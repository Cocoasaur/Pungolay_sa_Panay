"""Pose tracking with an automatic, reliable fallback backend.

Two backends implement the same PoseData contract:

* "mediapipe" -- MediaPipe Tasks PoseLandmarker (GPU delegate first, CPU
  second). This is the primary backend; it is fast and produces 3D depth
  (z) per landmark, which powers punch detection. On some platforms the GPU
  delegate can stall or deadlock mid-session (known issue with the Mesa/EGL
  stack on certain AMD machines); every detect therefore runs with a short
  watchdog and after a few stalls the tracker permanently migrates to the
  cv2 backend instead of freezing the game.

* "cv2" -- OpenCV DNN with a YOLO11n-pose ONNX model (CPU only). Deterministic
  and portable; landmarks are 2D (z = 0). Used automatically when mediapipe
  is unavailable or proves unstable on the host.

Both backends emit landmarks indexed with the MediaPipe convention (the
person's LEFT side appears on the RIGHT side of the frame).
"""

from __future__ import annotations

import logging
import math
import time
import os
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config

log = logging.getLogger(__name__)

# MediaPipe pose landmark indices we care about
LM_NOSE = 0
LM_LEFT_SHOULDER = 11
LM_RIGHT_SHOULDER = 12
LM_LEFT_ELBOW = 13
LM_RIGHT_ELBOW = 14
LM_LEFT_WRIST = 15
LM_RIGHT_WRIST = 16
LM_LEFT_HIP = 23
LM_RIGHT_HIP = 24

# Bones for the debug skeleton drawing (index pairs)
SKELETON = [
    (LM_NOSE, 9),
    (9, 10),
    (10, LM_RIGHT_SHOULDER),
    (LM_NOSE, 8),
    (8, 7),
    (7, LM_LEFT_SHOULDER),
    (LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER),
    (LM_LEFT_SHOULDER, LM_LEFT_ELBOW),
    (LM_LEFT_ELBOW, LM_LEFT_WRIST),
    (LM_RIGHT_SHOULDER, LM_RIGHT_ELBOW),
    (LM_RIGHT_ELBOW, LM_RIGHT_WRIST),
    (LM_LEFT_SHOULDER, LM_LEFT_HIP),
    (LM_RIGHT_SHOULDER, LM_RIGHT_HIP),
    (LM_LEFT_HIP, LM_RIGHT_HIP),
    (LM_LEFT_HIP, 25),
    (25, 27),
    (27, 29),
    (29, 31),
    (LM_RIGHT_HIP, 26),
    (26, 28),
    (28, 30),
    (30, 32),
]

# YOLO-pose COCO keypoint index -> MediaPipe index (only the ones we use)
_COCO_TO_MP = {
    0: LM_NOSE,
    5: LM_LEFT_SHOULDER,
    6: LM_RIGHT_SHOULDER,
    7: LM_LEFT_ELBOW,
    8: LM_RIGHT_ELBOW,
    9: LM_LEFT_WRIST,
    10: LM_RIGHT_WRIST,
    11: LM_LEFT_HIP,
    12: LM_RIGHT_HIP,
}

_CV2_MODEL_URL = (
    "https://github.com/ultralytics/assets/releases/download/" "v8.3.0/yolo11n-pose.onnx"
)

# how long a single detect may take before it counts as a stall
_DETECT_TIMEOUT = 0.6
# stalls (consecutive or not) before migrating away from mediapipe
_MEDIA_MPIPE_MAX_STALLS = 3


@dataclass
class PoseData:
    """Normalized pose landmarks + derived metrics for one frame.

    `landmarks` maps landmark index -> (x, y, z, visibility) in normalized
    image coordinates (0..1), matching the mediapipe convention where the
    person's LEFT side appears on the RIGHT side of the frame. z is 0 for
    the 2D (cv2) backend; `is_2d` tells gesture detection to use the 2D
    punch heuristic instead of the depth-based one.
    """

    present: bool
    landmarks: Dict[int, Tuple[float, float, float, float]] = field(default_factory=dict)
    body_confidence: float = 0.0
    shoulder_width: float = 0.0  # normalized
    torso_height: float = 0.0  # normalized
    body_center_x: float = 0.5  # normalized
    body_center_y: float = 0.5  # normalized
    frame_w: int = 0
    frame_h: int = 0
    is_2d: bool = False
    raw_landmarks: Dict[int, Tuple[float, float, float, float]] = field(default_factory=dict)

    def lm(self, index: int) -> Optional[Tuple[float, float, float, float]]:
        return self.landmarks.get(index)


class PoseTracker:
    """Wraps pose detection behind a simple process() call."""

    def __init__(self, model_path: str = config.POSE_MODEL_PATH) -> None:
        self.model_path = model_path
        self.available = False
        self.backend = "none"
        self.error = ""
        self._landmarker = None
        self._net = None
        self._stalls = 0
        self._last_filter_time = None
        self._smoothed_landmarks: Dict[int, Tuple[float, float, float, float]] = {}

    # ------------------------------------------------------------------
    # initialization with watchdog + self-test
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        """Build the best backend available. Never blocks forever."""
        backend_pref = config.POSE_BACKEND
        if backend_pref == "cv2":
            return self._init_cv2()
        if backend_pref == "mediapipe":
            return self._init_mediapipe()
        # "auto": mediapipe is battle-tested on Windows; elsewhere it is
        # verified inside a subprocess, because a deadlocked detect holds
        # the GIL and would freeze the game (observed on AMD/Mesa Linux).
        if sys.platform == "win32":
            if self._init_mediapipe():
                return True
            return self._init_cv2()
        if self._mediapipe_selftest_subprocess() and self._init_mediapipe():
            return True
        log.warning("MediaPipe pose self-test failed; using the OpenCV backend")
        return self._init_cv2()

    def _mediapipe_selftest_subprocess(self) -> bool:
        """Run the mediapipe self-test in a child process (it may hang)."""
        import subprocess

        cmd = [sys.executable, "-m", "camera.pose_selftest"]
        env = dict(os.environ)
        env["PYTHONPATH"] = config.BASE_DIR
        try:
            proc = subprocess.run(
                cmd,
                cwd=config.BASE_DIR,
                env=env,
                timeout=config.POSE_SELFTEST_TIMEOUT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    # -- mediapipe -----------------------------------------------------
    def _init_mediapipe(self) -> bool:
        try:
            from mediapipe.tasks import python as mp
            from mediapipe.tasks.python import vision
        except ImportError:
            self.error = "mediapipe not installed"
            return False

        for delegate_name, delegate in (
            ("GPU", mp.BaseOptions.Delegate.GPU),
            ("CPU", mp.BaseOptions.Delegate.CPU),
        ):
            result: Dict[str, object] = {}

            def build() -> None:
                try:
                    base = mp.BaseOptions(model_asset_path=self.model_path, delegate=delegate)
                    opts = vision.PoseLandmarkerOptions(
                        base_options=base,
                        running_mode=vision.RunningMode.IMAGE,
                        num_poses=1,
                        min_pose_detection_confidence=0.5,
                        min_pose_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    result["landmarker"] = vision.PoseLandmarker.create_from_options(opts)
                except Exception as exc:  # noqa: BLE001
                    result["error"] = str(exc)

            thread = threading.Thread(target=build, daemon=True)
            thread.start()
            thread.join(timeout=config.POSE_CREATE_TIMEOUT)
            if "landmarker" in result:
                self._landmarker = result["landmarker"]
                self.available = True
                self.backend = "mediapipe"
                log.info("Pose tracking initialized (mediapipe, %s delegate)", delegate_name)
                return True
            if "error" in result:
                self.error = f"{delegate_name} delegate failed: {result['error']}"
            else:
                self.error = f"{delegate_name} delegate timed out"

        self._landmarker = None
        log.warning("Pose tracking unavailable: %s", self.error)
        return False

    def _close_mediapipe(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:  # noqa: BLE001
                pass
            self._landmarker = None

    # -- cv2 (OpenCV DNN, YOLO11n-pose, CPU) ---------------------------
    def _init_cv2(self) -> bool:
        path = config.POSE_CV2_MODEL_PATH
        if not os.path.exists(path):
            log.info("Downloading the OpenCV pose model (%s)...", _CV2_MODEL_URL)
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                urllib.request.urlretrieve(_CV2_MODEL_URL, path)
            except Exception as exc:  # noqa: BLE001
                self.error = f"cv2 model download failed: {exc}"
                log.warning("%s", self.error)
                return False
        try:
            net = cv2.dnn.readNetFromONNX(path)
        except Exception as exc:  # noqa: BLE001
            self.error = f"cv2 model load failed: {exc}"
            log.warning("%s", self.error)
            return False
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net = net
        self.available = True
        self.backend = "cv2"
        log.info("Pose tracking initialized (OpenCV DNN backend)")
        return True

    def _ensure_cv2(self) -> bool:
        if self._net is None:
            return self._init_cv2()
        return True

    # ------------------------------------------------------------------
    # processing
    # ------------------------------------------------------------------
    def process(self, bgr_frame: np.ndarray) -> PoseData:
        """Detect a pose in a BGR frame and derive body metrics."""
        frame_w, frame_h = bgr_frame.shape[1], bgr_frame.shape[0]
        empty = PoseData(present=False, frame_w=frame_w, frame_h=frame_h)
        if self.backend == "cv2":
            landmarks = self._detect_cv2(bgr_frame)
            if not landmarks:
                return empty
            data = self._derive_metrics(landmarks, frame_w, frame_h)
            data.is_2d = True
            return data
        if self._landmarker is None:
            if self._ensure_cv2():
                return self.process(bgr_frame)
            return empty
        pose = self._detect_mediapipe(bgr_frame, timeout=_DETECT_TIMEOUT)
        if pose is None:
            # the watchdog fired: this host is not safe for mediapipe
            self._stalls += 1
            if self._stalls >= _MEDIA_MPIPE_MAX_STALLS:
                log.warning(
                    "MediaPipe detect stalled %d times; migrating to " "the OpenCV backend",
                    self._stalls,
                )
                self._close_mediapipe()
                self._ensure_cv2()
            return empty
        self._stalls = 0
        return pose

    def _detect_mediapipe(self, bgr_frame: np.ndarray, timeout: float) -> Optional[PoseData]:
        """Run one detect with a watchdog; None means the call stalled."""
        result: Dict[str, PoseData] = {}

        def run() -> None:
            try:
                from mediapipe.tasks.python import vision
                from mediapipe.tasks.python.vision.core.image import Image, ImageFormat

                rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                # Fresh Image per call: GPU tensors allow only a single write.
                image = Image(image_format=ImageFormat.SRGB, data=rgb)
                detected = self._landmarker.detect(image)
                if not detected.pose_landmarks:
                    result["pose"] = PoseData(
                        present=False, frame_w=bgr_frame.shape[1], frame_h=bgr_frame.shape[0]
                    )
                    return
                landmarks = detected.pose_landmarks[0]
                out: Dict[int, Tuple[float, float, float, float]] = {}
                for index, lm in enumerate(landmarks):
                    visibility = getattr(lm, "visibility", None)
                    visibility = float(visibility) if visibility is not None else 0.0
                    out[index] = (float(lm.x), float(lm.y), float(lm.z), visibility)
                result["pose"] = self._derive_metrics(out, bgr_frame.shape[1], bgr_frame.shape[0])
            except Exception:
                log.exception("Pose processing failed")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout)
        return result.get("pose")

    # ------------------------------------------------------------------
    # cv2 (YOLO11n-pose) detection
    # ------------------------------------------------------------------
    def _detect_cv2(self, bgr_frame: np.ndarray) -> Dict[int, Tuple[float, float, float, float]]:
        if self._net is None:
            return {}
        try:
            h, w = bgr_frame.shape[:2]
            # Letterbox to the model's square input, centered exactly as the
            # model was trained.  The inverse transform below is required
            # before drawing or using the normalized keypoints.
            scale = 640 / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(bgr_frame, (new_w, new_h))
            canvas = np.full((640, 640, 3), 114, dtype=np.uint8)
            pad_x = (640 - new_w) // 2
            pad_y = (640 - new_h) // 2
            canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
            blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (640, 640), (0, 0, 0), swapRB=True)
            self._net.setInput(blob)
            out = self._net.forward()  # (1, 56, 8400)

            preds = out[0].T  # (8400, 56)
            scores = preds[:, 4]
            best = int(np.argmax(scores))
            if scores[best] < config.POSE_CV2_PERSON_SCORE:
                return {}

            kpts = preds[best, 5:].reshape(17, 3)

            # absolute normalized coordinates in the original frame
            # (remove letterbox padding, then map model pixels to source)
            out_map: Dict[int, Tuple[float, float, float, float]] = {}
            for ck, mk in _COCO_TO_MP.items():
                kx, ky, kconf = kpts[ck]
                if kconf < config.POSE_CV2_KEYPOINT_CONF:
                    continue
                x, y = _unletterbox_point(kx, ky, scale, pad_x, pad_y, w, h)
                out_map[mk] = (x, y, 0.0, float(kconf))
            if not out_map:
                return {}
            return out_map
        except Exception:
            log.exception("CV2 pose processing failed")
            return {}

    # ------------------------------------------------------------------
    # shared metrics
    # ------------------------------------------------------------------
    def _derive_metrics(
        self,
        raw_landmarks: Dict[int, Tuple[float, float, float, float]],
        frame_w: int,
        frame_h: int,
    ) -> PoseData:
        """Compute body confidence, shoulder width, torso height, center with smoothed landmarks."""
        smoothed = {}
        now = time.monotonic()
        dt = (
            1 / 30
            if self._last_filter_time is None
            else max(0.001, min(0.1, now - self._last_filter_time))
        )
        self._last_filter_time = now
        alpha = config.TRACKING_SMOOTHING_FACTOR
        arms = {LM_LEFT_ELBOW, LM_RIGHT_ELBOW, LM_LEFT_WRIST, LM_RIGHT_WRIST}
        max_jump = config.MAX_LANDMARK_JUMP

        for k, lm in raw_landmarks.items():
            if k in arms and lm[3] < config.POSE_MIN_LANDMARK_VIS:
                continue
            # Reject impossible shoulder-to-hand chains, not fast valid motion.
            shoulder_id = (
                LM_LEFT_SHOULDER if k in (LM_LEFT_ELBOW, LM_LEFT_WRIST) else LM_RIGHT_SHOULDER
            )
            shoulder = raw_landmarks.get(shoulder_id)
            if k in arms and shoulder:
                hips = [raw_landmarks.get(i) for i in (LM_LEFT_HIP, LM_RIGHT_HIP)]
                torso = abs(shoulder[1] - sum(p[1] for p in hips) / 2) if all(hips) else 0.4
                limit = max(0.25, torso * 2.2)
                if math.hypot(lm[0] - shoulder[0], lm[1] - shoulder[1]) > limit:
                    continue
                if k in (LM_LEFT_WRIST, LM_RIGHT_WRIST):
                    elbow = raw_landmarks.get(
                        LM_LEFT_ELBOW if k == LM_LEFT_WRIST else LM_RIGHT_ELBOW
                    )
                    if elbow and math.hypot(lm[0] - elbow[0], lm[1] - elbow[1]) > max(
                        0.18, torso * 1.6
                    ):
                        continue
            if k in self._smoothed_landmarks:
                prev = self._smoothed_landmarks[k]

                alpha_use = alpha
                if lm[3] < config.TRACKING_CONFIDENCE_THRESHOLD:
                    alpha_use *= 0.2

                dx = lm[0] - prev[0]
                dy = lm[1] - prev[1]
                dz = lm[2] - prev[2]
                dist = (dx**2 + dy**2 + dz**2) ** 0.5

                if k in arms:
                    fast = dist / dt > 0.6 and lm[3] >= config.TRACKING_CONFIDENCE_THRESHOLD
                    tau = config.ARM_FILTER_FAST if fast else config.ARM_FILTER_SLOW
                    alpha_use = 1.0 - math.exp(-dt / tau)
                elif dist > max_jump:
                    alpha_use = 0.05

                sx = prev[0] * (1 - alpha_use) + lm[0] * alpha_use
                sy = prev[1] * (1 - alpha_use) + lm[1] * alpha_use
                sz = prev[2] * (1 - alpha_use) + lm[2] * alpha_use
                sv = prev[3] * (1 - alpha_use) + lm[3] * alpha_use
                smoothed[k] = (sx, sy, sz, sv)
            else:
                smoothed[k] = lm

        self._smoothed_landmarks = smoothed

        ls = smoothed.get(LM_LEFT_SHOULDER)
        rs = smoothed.get(LM_RIGHT_SHOULDER)
        lh = smoothed.get(LM_LEFT_HIP)
        rh = smoothed.get(LM_RIGHT_HIP)
        nose = smoothed.get(LM_NOSE)

        data = PoseData(
            present=True,
            landmarks=smoothed,
            raw_landmarks=raw_landmarks,
            frame_w=frame_w,
            frame_h=frame_h,
        )

        visible = [
            lm
            for lm in (ls, rs, lh, rh, nose)
            if lm is not None and lm[3] > config.POSE_MIN_LANDMARK_VIS
        ]
        if not visible:
            data.present = False
            return data
        data.body_confidence = sum(v[3] for v in visible) / len(visible)

        if ls and rs:
            data.shoulder_width = abs(ls[0] - rs[0])
        mid_shoulder = _midpoint(ls, rs)
        mid_hip = _midpoint(lh, rh)
        if mid_shoulder and mid_hip:
            data.torso_height = abs(mid_shoulder[1] - mid_hip[1])

        # weighted body center: configured in config so combat motion can
        # favour stable hips over shoulders that move during punches/guards.
        parts, weights = [], []
        for name, lm in (("shoulders", mid_shoulder), ("hips", mid_hip), ("nose", nose)):
            weight = config.BODY_CENTER_WEIGHTS.get(name, 0.0)
            if lm is not None and weight > 0.0:
                parts.append(lm[0])
                weights.append(weight)
        if parts:
            data.body_center_x = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        if mid_shoulder and mid_hip:
            data.body_center_y = (mid_shoulder[1] + mid_hip[1]) / 2
        return data

    # ------------------------------------------------------------------
    # debug rendering (used by the CAMERA DEBUG view)
    # ------------------------------------------------------------------
    def draw_debug_frame(
        self, bgr_frame: np.ndarray, pose: PoseData, raw: bool = False
    ) -> np.ndarray:
        """Draw landmarks, skeleton, bounding box and center line on a copy."""
        out = bgr_frame.copy()
        if not pose.present:
            return out
        w, h = out.shape[1], out.shape[0]
        pts: Dict[int, Tuple[int, int]] = {}
        landmarks = pose.raw_landmarks if raw and pose.raw_landmarks else pose.landmarks
        for index, (x, y, _z, vis) in landmarks.items():
            if vis > config.POSE_MIN_LANDMARK_VIS:
                pts[index] = (int(x * w), int(y * h))

        for a, b in SKELETON:
            if a in pts and b in pts:
                color = (
                    config.ARM_LEFT_COLOR
                    if a in (LM_LEFT_SHOULDER, LM_LEFT_ELBOW)
                    and b in (LM_LEFT_ELBOW, LM_LEFT_WRIST)
                    else (
                        config.ARM_RIGHT_COLOR
                        if a in (LM_RIGHT_SHOULDER, LM_RIGHT_ELBOW)
                        and b in (LM_RIGHT_ELBOW, LM_RIGHT_WRIST)
                        else (140, 200, 90)
                    )
                )
                cv2.line(out, pts[a], pts[b], color[::-1], 2)

        for index, (x, y) in pts.items():
            color = (
                config.ARM_LEFT_COLOR[::-1]
                if index == LM_LEFT_WRIST
                else config.ARM_RIGHT_COLOR[::-1] if index == LM_RIGHT_WRIST else (120, 220, 120)
            )
            cv2.circle(out, (x, y), 3, color, -1)
            if index in (LM_LEFT_WRIST, LM_RIGHT_WRIST):
                cv2.putText(
                    out,
                    "LEFT" if index == LM_LEFT_WRIST else "RIGHT",
                    (max(0, x - 15), max(15, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    1,
                    cv2.LINE_AA,
                )

        ls, rs = pts.get(LM_LEFT_SHOULDER), pts.get(LM_RIGHT_SHOULDER)
        lh, rh = pts.get(LM_LEFT_HIP), pts.get(LM_RIGHT_HIP)
        xs = [p[0] for p in (ls, rs, lh, rh) if p]
        ys = [p[1] for p in (ls, rs, lh, rh) if p]
        if xs and ys:
            min_x, max_x = max(0, min(xs) - 30), min(w - 1, max(xs) + 30)
            min_y, max_y = max(0, min(ys) - 60), min(h - 1, max(ys) + 40)
            cv2.rectangle(out, (min_x, min_y), (max_x, max_y), (200, 200, 90), 1)

        cx = int(pose.body_center_x * w)
        cv2.line(out, (cx, 0), (cx, h), (90, 160, 220), 1)
        return out

    def close(self) -> None:
        self._close_mediapipe()
        self._net = None


def _midpoint(
    a: Optional[Tuple[float, float, float, float]], b: Optional[Tuple[float, float, float, float]]
):
    if a is None or b is None:
        return None
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2, 1.0)


def _unletterbox_point(
    kx: float, ky: float, scale: float, pad_x: int, pad_y: int, source_w: int, source_h: int
) -> Tuple[float, float]:
    """Convert one 640x640 model keypoint back to source-normalized space."""
    x = (kx - pad_x) / (scale * source_w)
    y = (ky - pad_y) / (scale * source_h)
    return max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y)))

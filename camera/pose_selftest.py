"""MediaPipe reliability self-test (run as a subprocess by PoseTracker).

A deadlocked MediaPipe detect holds the GIL, so the only safe way to judge
whether this machine can run MediaPipe is inside a throwaway process: the
parent watches us with a timeout and treats a hang as a failure.

Exit code 0 = MediaPipe is reliable here, 1 = not reliable (or absent).
"""

from __future__ import annotations

import sys
import threading

import numpy as np

_ATTEMPTS = 25
_PER_CALL_TIMEOUT = 1.5


def _run_selftest() -> int:
    from mediapipe.tasks import python as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision.core.image import Image, ImageFormat

    for delegate in (mp.BaseOptions.Delegate.GPU, mp.BaseOptions.Delegate.CPU):
        try:
            base = mp.BaseOptions(
                model_asset_path="assets/models/pose_landmarker_lite.task",
                delegate=delegate)
            opts = vision.PoseLandmarkerOptions(
                base_options=base, running_mode=vision.RunningMode.IMAGE,
                num_poses=1)
            lm = vision.PoseLandmarker.create_from_options(opts)
        except Exception:
            continue

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        stalls = 0
        for _ in range(_ATTEMPTS):
            done = {}
            def run() -> None:
                try:
                    lm.detect(Image(image_format=ImageFormat.SRGB, data=frame))
                    done["ok"] = True
                except Exception:
                    done["ok"] = False
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            thread.join(_PER_CALL_TIMEOUT)
            if "ok" not in done:
                stalls += 1
            if stalls >= 3:
                break
        try:
            lm.close()
        except Exception:
            pass
        return 0 if stalls < 3 else 1
    return 1


if __name__ == "__main__":
    sys.exit(_run_selftest())
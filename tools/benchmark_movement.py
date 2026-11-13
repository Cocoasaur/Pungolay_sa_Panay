"""Replay timestamped left-inset poses through baseline/current movement only.

Personal frames/landmarks are never written. Aggregate path metrics cannot
establish intent or live tracking accuracy; the inset contains old overlays.
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import config
from camera.pose_tracker import PoseTracker, PoseData, LM_LEFT_HIP, LM_RIGHT_HIP
from camera.calibration import CalibrationData
from camera.distance_estimator import DistanceEstimator
from camera.gesture_detector import GestureDetector
from camera.movement import MovementController
from core.game import Game
from core.tracking import TrackingData
from gameplay.player import Player


def baseline_module(ref, path, name):
    source = subprocess.check_output(["git", "show", ref + ":" + path], text=True)
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def fixture(cls, cal):
    game = cls.__new__(cls)
    game.settings = dict(config.DEFAULT_SETTINGS)
    game.gestures = GestureDetector()
    game.calibrator = types.SimpleNamespace(existing=cal)
    game.distance = DistanceEstimator(cal)
    game.dt = 1 / 30
    game.tracking = TrackingData.empty()
    game.last_tracking = game.tracking
    game.reset_tracking_position()
    return game


def main():
    p = argparse.ArgumentParser()
    p.add_argument("recording")
    p.add_argument("--model", required=True)
    p.add_argument("--roi", default="60,252,496,280")
    p.add_argument("--stride", type=int, default=2)
    p.add_argument("--baseline", default="68d74ca")
    p.add_argument("--output", default="/tmp/movement-metrics.json")
    a = p.parse_args()
    config.POSE_CV2_MODEL_PATH = a.model
    config.POSE_BACKEND = "cv2"
    tracker = PoseTracker()
    if not tracker.initialize():
        raise SystemExit("Model unavailable")
    cap = cv2.VideoCapture(a.recording)
    fps = cap.get(cv2.CAP_PROP_FPS)
    dt = a.stride / fps
    x, y, w, h = map(int, a.roi.split(","))
    poses = []
    inference = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        stamp = i / fps
        i += 1
        if (i - 1) % a.stride:
            continue
        roi = cv2.resize(frame[y : y + h, x : x + w], (640, 360))
        start = time.perf_counter()
        raw = tracker._detect_cv2(roi)
        inference.append((time.perf_counter() - start) * 1000)
        with patch("camera.pose_tracker.time.monotonic", return_value=stamp):
            pose = tracker._derive_metrics(raw, 640, 360)
        pose.is_2d = True
        poses.append((stamp, pose))
    cap.release()
    tracker.close()
    valid = [pose for _, pose in poses if pose.present][:30]
    cal = CalibrationData(
        shoulder_width=statistics.median(p.shoulder_width for p in valid),
        torso_height=statistics.median(p.torso_height for p in valid),
    )
    OldGame = baseline_module(a.baseline, "core/game.py", "baseline_game").Game
    OldPlayer = baseline_module(a.baseline, "gameplay/player.py", "baseline_player").Player
    hip_confidences = [
        min((pose.lm(i) or (0, 0, 0, 0))[3] for i in (LM_LEFT_HIP, LM_RIGHT_HIP))
        for _, pose in poses
    ]
    results = {}
    for name, GameClass, PlayerClass in [("before", OldGame, OldPlayer), ("after", Game, Player)]:
        game = fixture(GameClass, cal)
        player = PlayerClass(460)
        xs = []
        states = []
        statuses = []
        if name == "after":
            minimum = config.ARENA_MARGIN + config.FIGHTER_BODY_WIDTH / 2
            game.movement = MovementController((460 - minimum) / (1280 - 2 * minimum))
            game.states = types.SimpleNamespace(
                _stack=[types.SimpleNamespace(name="gameplay", player=player)]
            )
        for stamp, pose in poses:
            if pose.present:
                game.gestures.update(pose, dt, cal, now=stamp)
                ratio, level, scale = game.distance.update(
                    pose, dt, torso_only=True, freeze=game._arms_active(pose)
                )
                game._update_tracking_data(
                    pose, ratio, level, scale, dt, freeze_depth=game._arms_active(pose)
                )
                tracking = game.tracking
            else:
                if name == "after":
                    game.movement.lose()
                tracking = TrackingData.empty()
            # Isolate locomotion from attacks, hit stun, AI, and knockback.
            tracking.left_punch = tracking.right_punch = tracking.left_haymaker = (
                tracking.right_haymaker
            ) = tracking.guard = False
            player.update(dt, tracking, stamp)
            xs.append(player.x)
            states.append(player.state)
            statuses.append(tracking.movement_status)
        results[name] = {
            "path_pixels": round(sum(abs(b - a) for a, b in zip(xs, xs[1:])), 2),
            "range_pixels": round(max(xs) - min(xs), 2),
            "idle_walk_switches": sum(a != b for a, b in zip(states, states[1:])),
            "walking_samples": states.count("walk"),
            "holding_samples": statuses.count("HOLDING"),
            "lost_or_reacquiring_samples": sum(
                s in ("TRACKING LOST", "REACQUIRING") for s in statuses
            ),
        }
    result = {
        "baseline": a.baseline,
        "roi": [x, y, w, h],
        "duration_seconds": round(i / fps, 3),
        "samples": len(poses),
        "poses_present": sum(p.present for _, p in poses),
        "confident_hip_pairs": sum(c >= config.MOVEMENT_MIN_CONFIDENCE for c in hip_confidences),
        "hip_confidence_median": round(statistics.median(hip_confidences), 3),
        "sample_hz": round(fps / a.stride, 3),
        "inference_median_ms": round(statistics.median(inference), 2),
        "inference_p95_ms": round(sorted(inference)[int(len(inference) * 0.95)], 2),
        **results,
        "limitations": "Screen-recorded 496x280 camera inset with baked overlays, inferred initial torso calibration, no ground-truth intent; isolated locomotion excludes combat knockback/collisions. This is not live webcam latency or accuracy.",
    }
    Path(a.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

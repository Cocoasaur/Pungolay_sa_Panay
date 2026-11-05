"""Aggregate absolute-alignment replay; never writes personal frames/landmarks.

Blocked intervals are a named fixed-opponent simulation, not reconstructed
combat from the recording. The UI header gates out the final result screen.
"""

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
import config
from camera.movement import MovementController, camera_to_arena
from camera.pose_tracker import PoseTracker
from core.tracking import TrackingData
from gameplay.player import Player
from gameplay.enemy import Enemy
from gameplay.spacing import separate_fighters


def intervals(labels, dt):
    result = []
    for i, label in enumerate(labels):
        if result and result[-1]["status"] == label:
            result[-1]["end_s"] = round((i + 1) * dt, 3)
        else:
            result.append(
                {"start_s": round(i * dt, 3), "end_s": round((i + 1) * dt, 3), "status": label}
            )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording")
    parser.add_argument("--model", required=True)
    parser.add_argument("--roi", default="64,426,396,222")
    parser.add_argument("--header-roi", default="64,374,396,50")
    parser.add_argument("--baseline", default="a1df965")
    parser.add_argument("--output", default="/tmp/alignment-metrics.json")
    args = parser.parse_args()
    config.POSE_CV2_MODEL_PATH = args.model
    config.POSE_BACKEND = "cv2"
    tracker = PoseTracker()
    if not tracker.initialize():
        raise SystemExit("Pose model unavailable")
    source = subprocess.check_output(
        ["git", "show", args.baseline + ":camera/movement.py"], text=True
    )
    previous = types.ModuleType("baseline_movement")
    exec(compile(source, "baseline_movement", "exec"), previous.__dict__)
    cap = cv2.VideoCapture(args.recording)
    fps = cap.get(cv2.CAP_PROP_FPS)
    dt = 2 / fps
    x, y, w, h = map(int, args.roi.split(","))
    hx, hy, hw, hh = map(int, args.header_roi.split(","))
    controllers = {"before": previous.MovementController(), "after": MovementController()}
    players = {name: Player(460) for name in controllers}
    enemies = {name: Enemy(config.ENEMIES["jessie"], 820) for name in controllers}
    labels = []
    errors = {name: [] for name in controllers}
    targets = {name: [] for name in controllers}
    paths = {name: 0.0 for name in controllers}
    times = []
    header = None
    i = 0
    arena_min = config.ARENA_MARGIN + config.FIGHTER_BODY_WIDTH / 2
    arena_span = config.BASE_WIDTH - 2 * arena_min
    states = {name: [] for name in controllers}
    poses = 0
    shifted_samples = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        stamp = i / fps
        i += 1
        if (i - 1) % 2:
            continue
        banner = frame[hy : hy + hh, hx : hx + hw].astype(np.float32)
        if header is None:
            header = banner.copy()
        # Hit-stop shakes the complete game canvas, including the camera inset.
        # Locate its static header again before cropping each matched frame.
        sx = max(0, hx - 40)
        sy = max(0, hy - 40)
        search = frame[sy : hy + hh + 40, sx : hx + hw + 40].astype(np.float32)
        _, score, _, location = cv2.minMaxLoc(
            cv2.matchTemplate(search, header, cv2.TM_CCOEFF_NORMED)
        )
        if score < 0.8:
            labels.append("NO CAMERA INSET")
            continue
        dx = sx + location[0] - hx
        dy = sy + location[1] - hy
        shifted_samples += bool(dx or dy)
        roi = cv2.resize(frame[y + dy : y + dy + h, x + dx : x + dx + w], (640, 360))
        start = time.perf_counter()
        raw = tracker._detect_cv2(roi)
        times.append((time.perf_counter() - start) * 1000)
        with patch("camera.pose_tracker.time.monotonic", return_value=stamp):
            p = tracker._derive_metrics(raw, 640, 360)
        p.is_2d = True
        poses += p.present
        after_status = "TRACKING LOST"
        for name, movement in controllers.items():
            player = players[name]
            before_x = player.x
            target = movement.update(p, dt, mirror=True)
            valid = movement.valid
            if not valid:
                movement.position = (player.x - arena_min) / arena_span
                target = movement.position
            tracking = TrackingData(
                present=p.present, movement_valid=valid, horizontal_position=target
            )
            player.update(dt, tracking, stamp, defer_motion=True)
            wanted_x = player.x
            enemy = enemies[name]
            separate_fighters(player, enemy, before_x, enemy.x)
            blocked = wanted_x > player.x + 1e-6
            if name == "after":
                after_status = (
                    "VALID BLOCKED"
                    if valid and blocked
                    else "VALID UNBLOCKED" if valid else movement.state
                )
            player.finalize_motion(dt, before_x)
            paths[name] += abs(player.x - before_x)
            states[name].append(player.state)
            if valid:
                left = p.lm(23)
                right = p.lm(24)
                if left and right:
                    ideal = camera_to_arena(1 - (left[0] + right[0]) / 2)
                    errors[name].append(abs(target - ideal))
                    targets[name].append(target)
        labels.append(after_status)
    cap.release()
    tracker.close()
    aggregates = {
        status: {"samples": labels.count(status), "seconds": round(labels.count(status) * dt, 3)}
        for status in (
            "VALID UNBLOCKED",
            "VALID BLOCKED",
            "TRACKING LOST",
            "REACQUIRING",
            "NO CAMERA INSET",
        )
    }
    result = {
        "baseline": args.baseline,
        "duration_seconds": round(i / fps, 3),
        "samples": len(labels),
        "sample_hz": round(1 / dt, 3),
        "roi": [x, y, w, h],
        "camera_inset_pose_samples": poses,
        "shake_corrected_samples": shifted_samples,
        "inset_locator": "static-header normalized template match >= 0.8 within +/-40 pixels",
        "intervals": intervals(labels, dt),
        "status_counts": aggregates,
        "inference_median_ms": round(statistics.median(times), 2),
        "inference_p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2),
        "mapping": {
            name: {
                "valid_samples": len(errors[name]),
                "mean_target_error_vs_filtered_hip": (
                    round(statistics.mean(errors[name]), 5) if errors[name] else None
                ),
                "target_min": round(min(targets[name]), 5) if targets[name] else None,
                "target_max": round(max(targets[name]), 5) if targets[name] else None,
                "path_pixels": round(paths[name], 2),
                "idle_walk_switches": sum(a != b for a, b in zip(states[name], states[name][1:])),
            }
            for name in controllers
        },
        "collision_fixture": {
            "enemy_x": 820,
            "ai_and_attacks": False,
            "before_run": "fixed-opponent body blocking simulation",
            "after_run": "fixed-opponent body blocking simulation",
        },
        "limitations": "Screen-recorded low-resolution left camera inset with baked overlays, inferred model hips, no ground truth, fixed-opponent collision fixture rather than reconstructed recorded combat. Loss/reacquisition retain confidence checks. Target error includes median/dead-zone delay and is not live tracking accuracy or latency.",
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "intervals"}, indent=2))


if __name__ == "__main__":
    main()

"""Replay a recording's camera inset without exporting personal footage.

Usage: python tools/benchmark_tracking.py RECORDING --model MODEL --output /tmp/metrics.json
The recording is a screen capture, so the default ROI selects its camera inset.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import config
from camera.pose_tracker import PoseTracker, LM_LEFT_WRIST, LM_RIGHT_WRIST


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default="/tmp/tracking-metrics.json")
    parser.add_argument("--roi", default="2000,282,504,284")
    parser.add_argument("--stride", type=int, default=5)
    args = parser.parse_args()
    config.POSE_CV2_MODEL_PATH = args.model
    config.POSE_BACKEND = "cv2"
    tracker = PoseTracker()
    if not tracker.initialize():
        raise SystemExit("Pose model unavailable")
    video = cv2.VideoCapture(args.recording)
    fps = video.get(cv2.CAP_PROP_FPS)
    x, y, w, h = map(int, args.roi.split(","))
    index = 0
    present = 0
    times = []
    errors = []
    old_errors = []
    fast = []
    old = {}
    previous = {}
    preview = []
    while True:
        ok, frame = video.read()
        if not ok:
            break
        if index % args.stride:
            index += 1
            continue
        stamp = index / fps
        index += 1
        roi = cv2.resize(frame[y : y + h, x : x + w], (640, 360))
        start = time.perf_counter()
        raw = tracker._detect_cv2(roi)
        times.append((time.perf_counter() - start) * 1000)
        with patch("camera.pose_tracker.time.monotonic", return_value=stamp):
            pose = tracker._derive_metrics(raw, 640, 360)
        pose.is_2d = True
        present += int(pose.present)
        for side in (LM_LEFT_WRIST, LM_RIGHT_WRIST):
            point = raw.get(side)
            filtered = pose.lm(side)
            if point is None or filtered is None or point[3] < config.TRACKING_CONFIDENCE_THRESHOLD:
                continue
            if side not in old:
                old[side] = point
            dist = sum((point[i] - old[side][i]) ** 2 for i in range(3)) ** 0.5
            alpha = 0.05 if dist > config.MAX_LANDMARK_JUMP else config.TRACKING_SMOOTHING_FACTOR
            old[side] = tuple(old[side][i] * (1 - alpha) + point[i] * alpha for i in range(4))
            error = ((filtered[0] - point[0]) ** 2 + (filtered[1] - point[1]) ** 2) ** 0.5
            old_error = ((old[side][0] - point[0]) ** 2 + (old[side][1] - point[1]) ** 2) ** 0.5
            errors.append(error)
            old_errors.append(old_error)
            if side in previous:
                speed = sum((point[i] - previous[side][i]) ** 2 for i in range(2)) ** 0.5 / (
                    args.stride / fps
                )
                if speed > 0.6:
                    fast.append((error, old_error))
            previous[side] = point
    video.release()
    tracker.close()
    result = {
        "samples": len(times),
        "poses_present": present,
        "sample_hz": round(fps / args.stride, 2),
        "inference_median_ms": round(statistics.median(times), 2),
        "inference_p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2),
        "wrist_samples": len(errors),
        "fast_wrist_samples": len(fast),
        "filtered_error_mean_normalized": round(statistics.mean(errors), 5),
        "old_filter_error_mean_normalized": round(statistics.mean(old_errors), 5),
        "fast_filtered_error_mean_normalized": (
            round(statistics.mean(p[0] for p in fast), 5) if fast else None
        ),
        "fast_old_error_mean_normalized": (
            round(statistics.mean(p[1] for p in fast), 5) if fast else None
        ),
        "limitations": "Screen-recorded low-resolution inset includes baked tracking overlays; this measures inference/filter behavior, not live camera latency or ground-truth punch accuracy.",
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""One-time asset setup: pose model download + font bundling.

Runs automatically from scripts/setup.sh / setup.bat. The game works without
it (falling back to keyboard mode), but real pose tracking needs the model.
"""

from __future__ import annotations

import os
import shutil
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

POSE_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_lite/float16/1/pose_landmarker_lite.task")
CV2_POSE_URL = ("https://github.com/ultralytics/assets/releases/download/"
                "v8.3.0/yolo11n-pose.onnx")


def ensure_pose_model() -> None:
    path = config.POSE_MODEL_PATH
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        print(f"Pose model present ({os.path.getsize(path)//1024} KB).")
        return
    print("Downloading MediaPipe pose model (~5.7 MB)...")
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    try:
        urllib.request.urlretrieve(POSE_URL, path)
        print(f"Saved to {path}")
    except Exception as exc:
        print(f"Download failed: {exc}")
        print("The game will run in KEYBOARD MODE until the model is present.")


def ensure_cv2_pose_model() -> None:
    path = config.POSE_CV2_MODEL_PATH
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        print(f"CV2 pose model present ({os.path.getsize(path)//1024} KB).")
        return
    print("Downloading OpenCV pose model (yolo11n-pose, ~11 MB)...")
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    try:
        urllib.request.urlretrieve(CV2_POSE_URL, path)
        print(f"Saved to {path}")
    except Exception as exc:
        print(f"Download failed: {exc}")
        print("The game falls back to keyboard mode until the model is present.")


def bundle_fonts() -> None:
    """Copy an OFL-licensed sans-serif font into assets/fonts when the game
    does not ship one (Linux/macOS). Windows machines get the bundled copy."""
    if os.path.exists(os.path.join(config.FONTS_DIR, "LiberationSans-Regular.ttf")):
        print("Fonts present.")
        return
    candidates = [
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    os.makedirs(config.FONTS_DIR, exist_ok=True)
    for src in candidates:
        if os.path.exists(src):
            try:
                dst = os.path.join(config.FONTS_DIR, os.path.basename(src))
                shutil.copy(src, dst)
                print(f"Bundled font: {dst}")
            except OSError:
                pass


if __name__ == "__main__":
    ensure_pose_model()
    ensure_cv2_pose_model()
    bundle_fonts()
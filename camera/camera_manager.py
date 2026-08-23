"""OpenCV webcam capture with graceful failure handling.

The game must never crash because a camera is missing or was yanked out mid-
match. Every failure is surfaced as a status string; callers decide what to
show the player.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import cv2

import config

log = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, index: int = 0) -> None:
        self.index = index
        self._cap: Optional[cv2.VideoCapture] = None
        self.status = "UNINITIALIZED"
        self.width = config.CAMERA_WIDTH
        self.height = config.CAMERA_HEIGHT

    # ------------------------------------------------------------------
    def open(self, index: Optional[int] = None) -> bool:
        """Open the webcam. Returns True when frames are being delivered."""
        if index is not None:
            self.index = index
        self.release()
        try:
            self._cap = cv2.VideoCapture(self.index)
        except Exception:
            self._cap = None
        if self._cap is None or not self._cap.isOpened():
            self._cap = None
            self.status = "CAMERA NOT DETECTED"
            return False

        # Request a small frame; webcams often ignore this, so we also
        # downscale in read() to keep the vision pipeline cheap.
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ok, _frame = self._cap.read()
        if not ok:
            self.release()
            self.status = "CAMERA NOT DETECTED"
            return False
        self.status = "CONNECTED"
        return True

    def read(self) -> Tuple[bool, Optional[object]]:
        """Returns (ok, bgr_frame_at_640x360). Frame is None when failing."""
        if self._cap is None:
            return False, None
        try:
            ok, frame = self._cap.read()
        except Exception:
            ok = False
            frame = None
        if not ok or frame is None:
            self.status = "CAMERA LOST"
            return False, None
        self.status = "CONNECTED"
        h, w = frame.shape[:2]
        if w != config.CAMERA_WIDTH or h != config.CAMERA_HEIGHT:
            frame = cv2.resize(frame, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
        return True, frame

    def grab(self) -> bool:
        """Lightweight check: is the device still delivering frames?"""
        if self._cap is None:
            return False
        try:
            return bool(self._cap.grab())
        except Exception:
            return False

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self.status = "RELEASED"


def probe_cameras(max_index: int = 3) -> List[int]:
    """Return a list of camera indices that can actually be opened."""
    available = []
    for index in range(max_index + 1):
        try:
            cap = cv2.VideoCapture(index)
            if cap is not None and cap.isOpened():
                ok, _frame = cap.read()
                if ok:
                    available.append(index)
            if cap is not None:
                cap.release()
        except Exception:
            continue
    return available
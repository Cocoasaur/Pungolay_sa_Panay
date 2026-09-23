"""Background thread for continuous camera capture and pose inference.

Ensures the main game loop is never blocked by OpenCV reads or MediaPipe/YOLO
inference. Retains only the freshest frame to minimize input latency.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

import config
from camera.pose_tracker import PoseTracker, PoseData

log = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, pose_tracker: PoseTracker):
        self.pose_tracker = pose_tracker
        self.index = 0
        self._cap: Optional[cv2.VideoCapture] = None
        self.status = "UNINITIALIZED"
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_pose: Optional[PoseData] = None
        
        # Metrics
        self.fps_camera = 0.0
        self.fps_pose = 0.0
        self.time_capture = 0.0
        self.time_inference = 0.0
        self.time_total = 0.0

    def open(self, index: int) -> bool:
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

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        ok, _frame = self._cap.read()
        if not ok:
            self.release()
            self.status = "CAMERA NOT DETECTED"
            return False
            
        self.status = "CONNECTED"
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return True

    def _worker(self):
        last_cam_time = time.time()
        last_pose_time = time.time()
        
        while not self._stop_event.is_set():
            if self._cap is None:
                break
                
            t0 = time.time()
            ok, frame = self._cap.read()
            t1 = time.time()
            
            if not ok or frame is None:
                self.status = "CAMERA LOST"
                time.sleep(0.1)
                continue
                
            self.status = "CONNECTED"
            
            cam_now = time.time()
            self.fps_camera = 1.0 / max(0.001, cam_now - last_cam_time)
            last_cam_time = cam_now
            
            h, w = frame.shape[:2]
            if w != config.CAMERA_WIDTH or h != config.CAMERA_HEIGHT:
                frame = cv2.resize(frame, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
                
            self.time_capture = (t1 - t0) * 1000.0
            
            # Inference
            pose = None
            if self.pose_tracker.available:
                pose = self.pose_tracker.process(frame)
            t2 = time.time()
            
            pose_now = time.time()
            if self.pose_tracker.available:
                self.fps_pose = 1.0 / max(0.001, pose_now - last_pose_time)
            last_pose_time = pose_now
            
            self.time_inference = (t2 - t1) * 1000.0
            self.time_total = (t2 - t0) * 1000.0
            
            with self._lock:
                self._latest_frame = frame
                self._latest_pose = pose

    def read_latest(self) -> Tuple[bool, Optional[np.ndarray], Optional[PoseData]]:
        """Returns (is_camera_ok, frame, pose)"""
        with self._lock:
            ok = self.status == "CONNECTED"
            frame = self._latest_frame.copy() if self._latest_frame is not None else None
            pose = self._latest_pose
            return ok, frame, pose

    def release(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.status = "RELEASED"

def probe_cameras(max_index: int = 3) -> list[int]:
    available = []
    for index in range(max_index + 1):
        try:
            cap = cv2.VideoCapture(index)
            if cap is not None and cap.isOpened():
                if cap.read()[0]:
                    available.append(index)
                cap.release()
        except Exception:
            pass
    return available


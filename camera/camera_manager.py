"""Nonblocking camera lifecycle, latest-frame capture, and matched pose samples."""

from __future__ import annotations
from dataclasses import dataclass
import logging
import threading
import time
import cv2
import numpy as np
import config
from camera.pose_tracker import PoseData, PoseTracker

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraSample:
    frame_id: int
    captured_at: float
    inferred_at: float
    frame: np.ndarray
    pose: PoseData | None


class CameraManager:
    def __init__(self, pose_tracker: PoseTracker):
        self.pose_tracker = pose_tracker
        self.index = 0
        self._cap = None
        self.status = "UNINITIALIZED"
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._device_lock = threading.Lock()
        self._owned_devices = {}
        self._stop_event = threading.Event()
        self._generation = 0
        self._thread = None
        self._capture_thread = None
        self._open_thread = None
        self._init_thread = None
        self._latest_capture = None
        self._sample = None
        self._next_id = 0
        self.devices = [0]
        self.scanning = False
        self.fps_camera = self.fps_pose = 0.0
        self.time_capture = self.time_inference = self.time_total = 0.0
        self.dropped_frames = 0

    @property
    def pending(self):
        return self.status in ("CONNECTING", "LOADING TRACKING", "RELEASING")

    def request_open(self, index):
        if index == self.index and (
            self.pending
            or self.status
            in ("CONNECTED", "CAMERA LOST", "CAMERA NOT DETECTED", "POSE UNAVAILABLE")
        ):
            if (
                self.status == "CONNECTED"
                and self._cap is not None
                and not self.pose_tracker.available
            ):
                self._initialize_async(self._generation)
            return
        previous_threads = (
            self._capture_thread,
            self._thread,
            self._open_thread,
            self._init_thread,
        )
        self.release_async()
        self.index = index
        self._generation += 1
        generation = self._generation
        stop = self._stop_event = threading.Event()
        self.status = "CONNECTING"

        def connect():
            # Native device/model calls may finish late. Drain their owners in
            # this worker, never by waiting in an event handler.
            for thread in previous_threads:
                if thread and thread is not threading.current_thread():
                    thread.join()
            if not stop.is_set():
                self._connect(index, generation, stop, True)

        self._open_thread = threading.Thread(target=connect, daemon=True)
        self._open_thread.start()

    def _connect(self, index, generation, stop, initialize):
        cap = None
        try:
            with self._device_lock:
                if stop.is_set():
                    return False
                self._owned_devices[generation] = index
                cap = cv2.VideoCapture(index)
                if not cap.isOpened():
                    raise RuntimeError("Camera not detected")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            with self._lock:
                if stop.is_set() or generation != self._generation:
                    cap.release()
                    self._owned_devices.pop(generation, None)
                    return False
                self._cap = cap
                if index not in self.devices:
                    self.devices.append(index)
                self.status = "CONNECTED"
            self._capture_thread = threading.Thread(
                target=self._capture, args=(cap, generation, stop), daemon=True
            )
            self._thread = threading.Thread(
                target=self._infer, args=(generation, stop), daemon=True
            )
            self._capture_thread.start()
            self._thread.start()
            if initialize:
                self._initialize_async(generation)
            return True
        except Exception:
            if cap is not None:
                cap.release()
            self._owned_devices.pop(generation, None)
            if generation == self._generation:
                self._cap = None
                self.status = "CAMERA NOT DETECTED"
            return False

    def _initialize_async(self, generation):
        if self.pose_tracker.available or (self._init_thread and self._init_thread.is_alive()):
            return

        def initialize():
            if generation != self._generation or self._stop_event.is_set():
                return
            self.status = "LOADING TRACKING"
            try:
                ready = self.pose_tracker.initialize()
            except Exception:
                log.exception("Tracking initialization failed")
                ready = False
            if generation == self._generation and not self._stop_event.is_set():
                self.status = "CONNECTED" if ready else "POSE UNAVAILABLE"

        self._init_thread = threading.Thread(target=initialize, daemon=True)
        self._init_thread.start()

    def open(self, index):
        """Synchronous compatibility API; UI callers must use request_open."""
        self.release()
        self.index = index
        self._generation += 1
        self._stop_event = threading.Event()
        return self._connect(index, self._generation, self._stop_event, False)

    def _capture(self, cap, generation, stop):
        last = time.monotonic()
        try:
            while not stop.is_set():
                start = time.monotonic()
                ok, frame = cap.read()
                captured = time.monotonic()
                if stop.is_set() or generation != self._generation:
                    break
                if self.status == "CAMERA LOST" and ok:
                    self.status = "CONNECTED" if self.pose_tracker.available else "POSE UNAVAILABLE"
                if not ok or frame is None:
                    if generation == self._generation:
                        self.status = "CAMERA LOST"
                    stop.wait(0.05)
                    continue
                if frame.shape[1::-1] != (config.CAMERA_WIDTH, config.CAMERA_HEIGHT):
                    frame = cv2.resize(frame, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
                self.time_capture = (captured - start) * 1000
                self.fps_camera = 1 / max(captured - last, 0.001)
                last = captured
                with self._condition:
                    if stop.is_set() or generation != self._generation:
                        break
                    self._next_id += 1
                    self._latest_capture = (self._next_id, captured, frame)
                    self._condition.notify_all()
        finally:
            cap.release()
            self._owned_devices.pop(generation, None)
            if generation == self._generation:
                self._cap = None

    def _infer(self, generation, stop):
        previous_id = -1
        previous_time = time.monotonic()
        while not stop.is_set():
            with self._condition:
                self._condition.wait_for(
                    lambda: stop.is_set()
                    or (
                        self._latest_capture is not None and self._latest_capture[0] != previous_id
                    ),
                    timeout=0.1,
                )
                if stop.is_set():
                    break
                capture = self._latest_capture
            if capture is None or capture[0] == previous_id:
                continue
            frame_id, captured, frame = capture
            if previous_id >= 0:
                self.dropped_frames += max(0, frame_id - previous_id - 1)
            previous_id = frame_id
            start = time.monotonic()
            try:
                pose = self.pose_tracker.process(frame) if self.pose_tracker.available else None
            except Exception:
                log.exception("Pose inference failed")
                pose = None
            now = time.monotonic()
            self.time_inference = (now - start) * 1000
            self.time_total = (now - captured) * 1000
            self.fps_pose = 1 / max(now - previous_time, 0.001) if pose is not None else 0
            previous_time = now
            with self._lock:
                if generation == self._generation and not stop.is_set():
                    self._sample = CameraSample(frame_id, captured, now, frame, pose)

    def read_sample(self):
        with self._lock:
            sample = self._sample
            if sample is None:
                return None
            return CameraSample(
                sample.frame_id,
                sample.captured_at,
                sample.inferred_at,
                sample.frame.copy(),
                sample.pose,
            )

    def read_latest(self):
        sample = self.read_sample()
        return (
            self._cap is not None,
            sample.frame if sample else None,
            sample.pose if sample else None,
        )

    def release_async(self):
        self._generation += 1
        stop = self._stop_event
        stop.set()
        with self._condition:
            self._sample = self._latest_capture = None
            self._condition.notify_all()
        self._cap = None
        self.status = "RELEASED"

    def release(self):
        self.release_async()
        for thread in (self._capture_thread, self._thread, self._open_thread, self._init_thread):
            if thread and thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def scan_async(self):
        if self.scanning:
            return
        self.scanning = True

        def scan():
            found = []
            try:
                with self._device_lock:
                    for index in range(4):
                        if index in tuple(self._owned_devices.values()) or (
                            index == self.index and (self._cap is not None or self.pending)
                        ):
                            found.append(index)
                            continue
                        cap = None
                        try:
                            cap = cv2.VideoCapture(index)
                            if cap.isOpened() and cap.read()[0]:
                                found.append(index)
                        except Exception:
                            pass
                        finally:
                            if cap is not None:
                                cap.release()
                self.devices = found or [self.index]
            finally:
                self.scanning = False

        threading.Thread(target=scan, daemon=True).start()


def probe_cameras(max_index=3):
    """Compatibility helper for tools; menus use the asynchronous device cache."""
    available = []
    for index in range(max_index + 1):
        cap = None
        try:
            cap = cv2.VideoCapture(index)
            if cap.isOpened() and cap.read()[0]:
                available.append(index)
        except Exception:
            pass
        finally:
            if cap is not None:
                cap.release()
    return available

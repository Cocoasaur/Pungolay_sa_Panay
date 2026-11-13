"""Latest-only capture/inference and cancelable camera lifecycle."""

import time
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from camera.camera_manager import CameraManager


class CameraWorkerTests(unittest.TestCase):
    def test_slow_open_cancel_is_nonblocking_and_stale_result_is_closed(self):
        gate = threading.Event()
        started = threading.Event()
        released = threading.Event()

        class Cap:
            def isOpened(self):
                return True

            def set(self, *args):
                pass

            def release(self):
                released.set()

        def opening(_):
            started.set()
            gate.wait(2)
            return Cap()

        tracker = SimpleNamespace(available=False, initialize=lambda: True)
        camera = CameraManager(tracker)
        with patch("camera.camera_manager.cv2.VideoCapture", side_effect=opening):
            t = time.perf_counter()
            camera.request_open(0)
            self.assertLess(time.perf_counter() - t, 0.1)
            self.assertTrue(started.wait(1))
            t = time.perf_counter()
            camera.release_async()
            self.assertLess(time.perf_counter() - t, 0.1)
            gate.set()
            camera._open_thread.join(2)
        self.assertTrue(released.is_set())
        self.assertIsNone(camera._cap)
        self.assertEqual(camera.status, "RELEASED")

    def test_slow_model_initialization_does_not_block_or_overwrite_cancellation(self):
        started = threading.Event()
        finish = threading.Event()

        def initialize():
            started.set()
            finish.wait(1.15)
            return True

        camera = CameraManager(SimpleNamespace(available=False, initialize=initialize))
        camera.status = "CONNECTED"
        start = time.perf_counter()
        camera._initialize_async(camera._generation)
        self.assertLess(time.perf_counter() - start, 0.1)
        self.assertTrue(started.wait(1))
        self.assertEqual(camera.status, "LOADING TRACKING")
        camera.release_async()
        finish.set()
        camera._init_thread.join(1)
        self.assertEqual(camera.status, "RELEASED")

    def test_failed_open_is_not_retried_each_render_frame(self):
        camera = CameraManager(SimpleNamespace(available=False))
        camera.status = "CAMERA NOT DETECTED"
        with patch("camera.camera_manager.cv2.VideoCapture") as open_device:
            for _ in range(60):
                camera.request_open(0)
            open_device.assert_not_called()

    def test_capture_supersedes_frames_while_inference_is_busy(self):
        done = threading.Event()

        class Tracker:
            available = True

            def process(self, frame):
                time.sleep(0.015)
                return int(frame[0, 0, 0])

        class Cap:
            def read(self):
                time.sleep(0.001)
                return True, np.full(
                    (360, 640, 3), int(time.monotonic() * 1000) % 255, dtype=np.uint8
                )

            def release(self):
                done.set()

        camera = CameraManager(Tracker())
        camera._cap = Cap()
        camera._generation = 1
        stop = threading.Event()
        capture = threading.Thread(target=camera._capture, args=(camera._cap, 1, stop))
        infer = threading.Thread(target=camera._infer, args=(1, stop))
        capture.start()
        infer.start()
        try:
            deadline = time.monotonic() + 1
            while camera.dropped_frames == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            sample = camera.read_sample()
            self.assertIsNotNone(sample)
            self.assertEqual(sample.pose, int(sample.frame[0, 0, 0]))
            self.assertGreater(camera.dropped_frames, 0)
            self.assertGreaterEqual(sample.inferred_at, sample.captured_at)
        finally:
            stop.set()
            with camera._condition:
                camera._condition.notify_all()
            capture.join(1)
            infer.join(1)
        self.assertTrue(done.is_set())

    def test_scan_skips_active_camera_and_has_only_one_worker(self):
        camera = CameraManager(SimpleNamespace(available=True))
        camera._cap = object()
        camera.index = 1
        gate = threading.Event()
        opened = []

        class Cap:
            def isOpened(self):
                return False

            def release(self):
                pass

        def opening(i):
            opened.append(i)
            gate.wait(1)
            return Cap()

        with patch("camera.camera_manager.cv2.VideoCapture", side_effect=opening):
            camera.scan_async()
            camera.scan_async()
            gate.set()
            deadline = time.monotonic() + 1
            while camera.scanning and time.monotonic() < deadline:
                time.sleep(0.005)
        self.assertEqual(opened, [0, 2, 3])
        self.assertIn(1, camera.devices)

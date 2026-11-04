"""Fresh sample edges, stale rejection, and stable movement."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from camera.camera_manager import CameraSample
from camera.punch_boundary import punch_boundary
from test_punch_boundary import pose
import test_punch_boundary as fixtures


class FreshSampleTests(unittest.TestCase):
    setUp = fixtures.PunchMovementTests.setUp

    # Reuse the movement fixture; do not depend on rendering frequency.
    def sample(self, frame_id, stamp, data):
        frame = np.full((2, 2, 3), frame_id, dtype=np.uint8)
        sample = CameraSample(frame_id, stamp, stamp + 0.01, frame, data)
        self.game.camera = SimpleNamespace(read_sample=lambda: sample, _cap=object())
        with patch("core.game.time.monotonic", return_value=stamp + 0.02):
            return self.game.poll_camera(0.016)

    def test_duplicate_samples_emit_one_punch_and_keep_matched_frame(self):
        self.sample(1, 1, pose())
        fired = self.sample(2, 1.04, pose(left_x=0.8))
        self.assertTrue(fired.left_punch)
        repeated = self.sample(2, 1.04, pose(left_x=0.8))
        self.assertFalse(repeated.left_punch)
        self.assertFalse(self.game._sample_is_new)
        self.assertTrue(np.all(self.game.last_camera_frame == 2))

    def test_stale_samples_cannot_punch_and_hold_position_scale(self):
        self.sample(1, 1, pose())
        previous = self.game.tracking
        sample = CameraSample(2, 1.04, 1.1, np.zeros((2, 2, 3), dtype=np.uint8), pose(left_x=0.8))
        self.game.camera = SimpleNamespace(read_sample=lambda: sample, _cap=object())
        with patch("core.game.time.monotonic", return_value=1.5):
            data = self.game.poll_camera(0.016)
        self.assertFalse(data.left_punch)
        self.assertFalse(data.present)
        self.assertEqual(data.horizontal_position, previous.horizontal_position)
        self.assertEqual(data.player_scale, previous.player_scale)

    def test_duplicate_charge_samples_do_not_advance_time(self):
        tucked = pose(left_x=0.34, wrist_y=0.31)
        self.sample(1, 1, tucked)
        initial = self.game.gestures.left_hand.charge_time
        for _ in range(200):
            self.sample(1, 1, tucked)
        self.assertEqual(self.game.gestures.left_hand.charge_time, initial)
        self.assertFalse(self.game.tracking.charge_completed)

    def test_boundary_distance_is_independent_of_sensitivity(self):
        a = punch_boundary(pose(), self.calibration, sensitivity=0.5)
        b = punch_boundary(pose(), self.calibration, sensitivity=3)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a.x, 0.8)
        self.assertAlmostEqual(punch_boundary(pose(), self.calibration, reach_fraction=0.9).x, 0.86)

    def test_mirror_setting_never_swaps_anatomical_punch_events(self):
        for mirror in (True, False):
            self.setUp()
            self.game.settings["mirror_input"] = mirror
            self.sample(1, 1, pose())
            self.sample(2, 1.04, pose(left_x=0.8))
            self.assertTrue(self.game.tracking.left_punch)
            self.assertFalse(self.game.tracking.right_punch)

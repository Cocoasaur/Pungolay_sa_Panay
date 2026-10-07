"""Headless regression checks for camera-to-arena tracking."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import config
from camera.calibration import CalibrationData
from camera.distance_estimator import DistanceEstimator
from camera.gesture_detector import GestureDetector
from camera.pose_tracker import LM_LEFT_HIP, LM_RIGHT_HIP, _unletterbox_point
from core.game import Game
from core.tracking import TrackingData


class CameraTrackingTests(unittest.TestCase):
    def make_game(self):
        game = Game.__new__(Game)
        game.settings = {"mirror_input": True, "sensitivity": 1.0,
                         "smoothing": 0.55}
        game.gestures = GestureDetector()
        game.dt = 1.0 / 60.0
        game._smooth_x = config.DEPTH_NEUTRAL_HP
        game._resting_ratio = None
        game._resting_lateral = None
        game._stable_depth_delta = 0.0
        game._depth_freeze_remaining = 0.0
        game._last_lateral = None
        game.tracking = TrackingData.empty()
        return game

    @staticmethod
    def pose(center_x=0.5, shoulder_width=0.25, torso_height=0.20):
        hips = {LM_LEFT_HIP: (center_x - 0.04, 0.7, 0.0, 1.0),
                LM_RIGHT_HIP: (center_x + 0.04, 0.7, 0.0, 1.0)}
        return SimpleNamespace(present=True, body_center_x=center_x,
                               shoulder_width=shoulder_width,
                               torso_height=torso_height,
                               body_confidence=1.0, frame_w=640, frame_h=360,
                               lm=hips.get)

    def settle(self, game, pose, ratio, frames=240, **kwargs):
        for _ in range(frames):
            game._update_tracking_data(pose, ratio, "MEDIUM", 1.0,
                                       1.0 / 60.0, **kwargs)
        return game.tracking.horizontal_position

    def test_fight_reset_and_constant_pose_do_not_drift(self):
        game = self.make_game()
        game._smooth_x = 0.8
        game.reset_tracking_position()
        self.assertEqual(game._smooth_x, config.DEPTH_NEUTRAL_HP)
        resting = self.settle(game, self.pose(), 1.8)
        stable = self.settle(game, self.pose(), 1.8, frames=60)
        self.assertAlmostEqual(resting, config.DEPTH_NEUTRAL_HP, places=6)
        self.assertAlmostEqual(stable, resting, places=6)

    def test_lateral_and_depth_move_in_expected_directions(self):
        game = self.make_game()
        self.settle(game, self.pose(), 1.8)
        right = self.settle(game, self.pose(0.30), 1.8)
        self.assertGreater(right, config.DEPTH_NEUTRAL_HP + 0.15)
        left = self.settle(game, self.pose(0.70), 1.8)
        self.assertLess(left, config.DEPTH_NEUTRAL_HP - 0.15)

        game.reset_tracking_position()
        self.settle(game, self.pose(), 1.8)
        closer = self.settle(game, self.pose(), 2.05)
        self.assertGreater(closer, config.DEPTH_NEUTRAL_HP + 0.15)
        self.assertLess(closer, config.DEPTH_HP_MAX)
        farther = self.settle(game, self.pose(), 1.55)
        self.assertLess(farther, config.DEPTH_NEUTRAL_HP - 0.15)

    def test_raised_arms_hold_depth_but_keep_lateral_control(self):
        game = self.make_game()
        self.settle(game, self.pose(), 1.8)
        lateral_only = self.settle(game, self.pose(0.3), 1.8)
        game.reset_tracking_position()
        self.settle(game, self.pose(), 1.8)
        raised_arms = self.settle(game, self.pose(0.3), 2.2,
                                  frames=60, freeze_depth=True)
        self.assertAlmostEqual(raised_arms, lateral_only, places=4)

    def test_identical_calibration_keeps_distance_filter(self):
        calibration = CalibrationData()
        estimator = DistanceEstimator(calibration)
        estimator._smoothed = 1.75
        self.assertFalse(estimator.set_calibration(CalibrationData()))
        self.assertEqual(estimator._smoothed, 1.75)
        self.assertTrue(estimator.set_calibration(
            CalibrationData(shoulder_width=0.50, torso_height=0.40)))
        self.assertEqual(estimator._smoothed, 1.0)

    def test_raised_arms_use_torso_distance_only(self):
        calibration = CalibrationData(shoulder_width=0.45, torso_height=0.36)
        raised_arm_pose = self.pose(shoulder_width=0.15, torso_height=0.20)
        normal = DistanceEstimator(calibration).update(raised_arm_pose, 1.0)[0]
        torso_only = DistanceEstimator(calibration).update(
            raised_arm_pose, 1.0, torso_only=True)[0]
        self.assertGreater(normal, torso_only)
        self.assertAlmostEqual(torso_only, 0.36 / 0.20, places=4)

    def test_window_mouse_coordinates_follow_letterboxing(self):
        game = Game.__new__(Game)
        game.screen = SimpleNamespace(get_size=lambda: (1600, 1000))
        # 1600x1000 renders a 1600x900 canvas centered with 50px top/bottom bars.
        self.assertEqual(game.window_to_canvas((100, 175)), (80.0, 100.0))

    def test_opencv_letterbox_coordinates_map_back_to_the_body(self):
        # A 640x360 frame is centered vertically in the 640x640 model input.
        self.assertEqual(_unletterbox_point(320, 320, 1.0, 0, 140, 640, 360),
                         (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()

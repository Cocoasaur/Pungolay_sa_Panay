"""Punch boundaries must follow the body without turning punches into steps."""

import unittest
from types import SimpleNamespace

import numpy as np

import config
from camera.calibration import CalibrationData, Calibrator
from camera.distance_estimator import DistanceEstimator
from camera.gesture_detector import GestureDetector
from camera.pose_tracker import (
    LM_LEFT_ELBOW, LM_LEFT_HIP, LM_LEFT_SHOULDER, LM_LEFT_WRIST,
    LM_NOSE, LM_RIGHT_ELBOW, LM_RIGHT_HIP, LM_RIGHT_SHOULDER, LM_RIGHT_WRIST,
    PoseData,
)
from camera.punch_boundary import punch_boundary
from core.game import Game
from core.tracking import TrackingData


def pose(left_x=0.48, right_x=0.54, wrist_y=0.38, shift=0.0, scale=1.0):
    points = {
        LM_NOSE: (0.5, 0.12),
        LM_LEFT_SHOULDER: (0.48, 0.3), LM_RIGHT_SHOULDER: (0.52, 0.3),
        LM_LEFT_ELBOW: (0.50, 0.42), LM_RIGHT_ELBOW: (0.55, 0.42),
        LM_LEFT_WRIST: (left_x, wrist_y), LM_RIGHT_WRIST: (right_x, wrist_y),
        LM_LEFT_HIP: (0.45, 0.7), LM_RIGHT_HIP: (0.55, 0.7),
    }
    landmarks = {index: (0.5 + (x - 0.5) * scale + shift,
                         0.3 + (y - 0.3) * scale, 0.0, 1.0)
                 for index, (x, y) in points.items()}
    return PoseData(True, landmarks=landmarks, body_confidence=1.0,
                    shoulder_width=0.04 * scale, torso_height=0.4 * scale,
                    body_center_x=0.5 + shift, frame_w=640, frame_h=360, is_2d=True)


class PunchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.calibration = CalibrationData(torso_height=0.4, arm_length=0.4,
                                           punch_direction=1.0)
        self.detector = GestureDetector()
        self.now = 0.0

    def update(self, data, frames=1, dt=0.05):
        events = []
        for _ in range(frames):
            self.now += dt
            self.detector.update(data, dt, self.calibration, now=self.now)
            events.append((self.detector.left_punch, self.detector.right_punch,
                           self.detector.left_haymaker, self.detector.right_haymaker))
        return events

    def test_each_hand_crosses_once_and_must_retract(self):
        for hand in ("left", "right"):
            with self.subTest(hand=hand):
                self.detector = GestureDetector()
                self.update(pose(), 3)
                extended = pose(**{hand + "_x": 0.80})
                events = self.update(extended, 30)
                index = 0 if hand == "left" else 1
                self.assertEqual(sum(event[index] for event in events), 1)
                self.assertEqual(sum(event[1 - index] for event in events), 0)
                self.update(pose(), 8)
                self.assertTrue(any(event[index] for event in self.update(extended, 3)))

    def test_line_works_when_facing_image_left(self):
        self.calibration.punch_direction = -1.0
        self.update(pose(), 3)
        self.assertTrue(any(event[0] for event in self.update(pose(left_x=0.18), 3)))

    def test_line_follows_translation_and_distance_without_punches(self):
        base = punch_boundary(pose(), self.calibration)
        moved = punch_boundary(pose(shift=0.1, scale=1.5), self.calibration)
        self.assertAlmostEqual(moved.x, 0.6 + (base.x - 0.5) * 1.5)
        self.update(pose(), 3)
        for shift, scale in ((0.15, 1.0), (-0.1, 0.7), (0.0, 1.5)):
            self.assertFalse(any(any(event) for event in self.update(
                pose(shift=shift, scale=scale), 5)))

    def test_initial_extended_hand_and_raised_hand_do_not_punch(self):
        self.assertFalse(any(any(event) for event in self.update(pose(left_x=0.8), 10)))
        self.update(pose(), 3)
        self.assertFalse(any(any(event) for event in self.update(
            pose(left_x=0.8, wrist_y=0.05), 10)))

    def test_lost_wrist_requires_a_new_return_behind_the_line(self):
        self.update(pose(), 3)
        lost = pose()
        lost.landmarks[LM_LEFT_WRIST] = (0.8, 0.38, 0.0, 0.1)
        self.update(lost, 3)
        self.assertFalse(any(event[0] for event in self.update(pose(left_x=0.8), 10)))
        self.update(pose(), 3)
        self.assertTrue(any(event[0] for event in self.update(pose(left_x=0.8), 3)))

    def test_line_keeps_scale_when_hips_are_temporarily_missing(self):
        data = pose(scale=1.5)
        before = self.detector.boundary_for(data, self.calibration)
        del data.landmarks[LM_LEFT_HIP]
        del data.landmarks[LM_RIGHT_HIP]
        data.torso_height = 0.0
        after = self.detector.boundary_for(data, self.calibration)
        self.assertEqual(after, before)

    def test_charged_crossing_still_triggers_haymaker(self):
        self.update(pose(), 3)
        self.detector.left_hand.state = "CHARGED"
        self.detector.left_hand.charge_time = config.HAYMAKER_CHARGE_TIME
        events = self.update(pose(left_x=0.8), 5, dt=1.0 / 60.0)
        self.assertTrue(any(event[2] for event in events))
        self.assertFalse(any(event[0] for event in events))

    def test_3d_body_translation_does_not_count_as_wrist_punch(self):
        data = pose(left_x=0.8)
        data.is_2d = False
        wrist = data.landmarks[LM_LEFT_WRIST]
        data.landmarks[LM_LEFT_WRIST] = (wrist[0], wrist[1], -0.1, wrist[3])
        self.update(data, 3)
        events = []
        for _ in range(10):
            data.landmarks = {index: (x, y, z - 0.1, visibility)
                              for index, (x, y, z, visibility) in data.landmarks.items()}
            events.extend(self.update(data))
        self.assertFalse(any(any(event) for event in events))

    def test_3d_wrist_thrust_still_triggers_a_punch(self):
        data = pose(left_x=0.8)
        data.is_2d = False
        self.update(data, 3)
        wrist = data.landmarks[LM_LEFT_WRIST]
        data.landmarks[LM_LEFT_WRIST] = (wrist[0], wrist[1], -0.2, wrist[3])
        self.assertTrue(any(event[0] for event in self.update(data, 5, dt=1.0 / 60.0)))

    def test_preview_draws_the_actual_detection_line(self):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        data = pose()
        result = self.detector.draw_punch_boundary(frame, data, self.calibration)
        x = int(punch_boundary(data, self.calibration).x * 640)
        self.assertTrue(result[140, x].any())
        self.assertFalse(frame.any())

    def test_calibration_preserves_direction_and_loads_older_settings(self):
        self.assertEqual(CalibrationData.from_dict(self.calibration.to_dict()).punch_direction, 1.0)
        legacy = CalibrationData.from_dict({"lead_shoulder": "right"})
        self.assertEqual(punch_boundary(pose(), legacy).direction, -1.0)
        calibrator = Calibrator()
        calibrator._punch_directions = [-0.08, -0.10, -0.09]
        self.assertEqual(calibrator.finish().punch_direction, -1.0)


class PunchMovementTests(unittest.TestCase):
    def setUp(self):
        self.calibration = CalibrationData(torso_height=0.4, arm_length=0.4,
                                           punch_direction=1.0)
        game = Game.__new__(Game)
        game.settings = {"mirror_input": True, "sensitivity": 1.0, "smoothing": 0.55}
        game.gestures = GestureDetector()
        game.calibrator = SimpleNamespace(existing=self.calibration)
        game.distance = DistanceEstimator(self.calibration)
        game.dt = 0.05
        game.reset_tracking_position()
        game.tracking = TrackingData.empty()
        game._tracking_lost_time = 0.0
        game._pose_gone = True
        self.game = game

    def poll(self, data, frames=1):
        self.game.camera = SimpleNamespace(read_latest=lambda: (True, None, data))
        results = []
        for _ in range(frames):
            results.append(self.game.poll_camera(self.game.dt))
        return results

    def test_punch_and_recovery_do_not_shift_depth_or_contaminate_filter(self):
        self.poll(pose(wrist_y=0.75), 20)
        resting = self.game.tracking.horizontal_position
        self.poll(pose(), 3)
        extended = pose(left_x=0.8)
        extended.shoulder_width = 0.005
        extended.torso_height = 0.25
        results = self.poll(extended, 20)
        self.assertTrue(any(data.left_punch for data in results))
        self.assertTrue(all(abs(data.horizontal_position - resting) < 1e-6 for data in results))
        self.assertAlmostEqual(self.game.distance._smoothed, 1.0)
        recovering = pose(wrist_y=0.75)
        recovering.torso_height = 0.25
        self.poll(recovering, 2)
        self.poll(pose(wrist_y=0.75), 20)
        self.assertAlmostEqual(self.game.tracking.horizontal_position, resting)
        self.assertAlmostEqual(self.game.distance._smoothed, 1.0)

    def test_shoulder_turn_does_not_move_boxer_but_hip_step_does(self):
        self.poll(pose(wrist_y=0.75), 20)
        turned = pose(wrist_y=0.75)
        turned.shoulder_width = 0.005
        self.poll(turned, 20)
        self.assertAlmostEqual(self.game.tracking.horizontal_position, config.DEPTH_NEUTRAL_HP)
        self.poll(pose(wrist_y=0.75, shift=-0.15), 20)
        self.assertGreater(self.game.tracking.horizontal_position, config.DEPTH_NEUTRAL_HP + 0.1)

    def test_missing_hips_hold_movement_during_punch(self):
        self.poll(pose(wrist_y=0.75), 20)
        extended = pose(left_x=0.8)
        del extended.landmarks[LM_LEFT_HIP]
        del extended.landmarks[LM_RIGHT_HIP]
        extended.body_center_x = 0.1
        self.poll(extended, 20)
        self.assertAlmostEqual(self.game.tracking.horizontal_position, config.DEPTH_NEUTRAL_HP)


if __name__ == "__main__":
    unittest.main()

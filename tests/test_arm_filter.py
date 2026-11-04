"""Adaptive anatomical arm filters without slowing the torso."""

import unittest
from unittest.mock import patch
from camera.pose_tracker import PoseTracker, LM_LEFT_WRIST, LM_RIGHT_WRIST, LM_LEFT_HIP
from test_punch_boundary import pose


class ArmFilterTests(unittest.TestCase):
    def test_fast_confident_arm_reaches_ninety_percent_in_two_samples(self):
        tracker = PoseTracker()
        base = pose().landmarks
        with patch("camera.pose_tracker.time.monotonic", side_effect=[0, 1 / 60, 2 / 60]):
            tracker._derive_metrics(base, 640, 360)
            extended = pose(left_x=0.8).landmarks
            first = tracker._derive_metrics(extended, 640, 360)
            second = tracker._derive_metrics(extended, 640, 360)
        ratio = (second.lm(LM_LEFT_WRIST)[0] - 0.48) / (0.8 - 0.48)
        self.assertGreaterEqual(ratio, 0.90)
        self.assertGreater(first.lm(LM_LEFT_WRIST)[0], 0.65)
        self.assertAlmostEqual(second.lm(LM_RIGHT_WRIST)[0], 0.54)

    def test_idle_jitter_is_smoothed_and_hips_keep_steady_filter(self):
        tracker = PoseTracker()
        base = pose().landmarks
        with patch("camera.pose_tracker.time.monotonic", side_effect=[0, 1 / 60]):
            tracker._derive_metrics(base, 640, 360)
            moved = dict(base)
            moved[LM_LEFT_WRIST] = (0.482, 0.38, 0, 1)
            moved[LM_LEFT_HIP] = (0.75, 0.7, 0, 1)
            data = tracker._derive_metrics(moved, 640, 360)
        self.assertLess(data.lm(LM_LEFT_WRIST)[0] - 0.48, 0.001)
        self.assertLess(data.lm(LM_LEFT_HIP)[0] - 0.45, 0.02)

    def test_occlusion_rejects_a_wrist_and_recovery_does_not_mix_arms(self):
        tracker = PoseTracker()
        tracker._derive_metrics(pose().landmarks, 640, 360)
        raw = pose(left_x=0.8, right_x=0.2).landmarks
        raw[LM_LEFT_WRIST] = (0.8, 0.38, 0, 0.1)
        lost = tracker._derive_metrics(raw, 640, 360)
        self.assertIsNone(lost.lm(LM_LEFT_WRIST))
        recovered = tracker._derive_metrics(pose(left_x=0.8, right_x=0.2).landmarks, 640, 360)
        self.assertAlmostEqual(recovered.lm(LM_LEFT_WRIST)[0], 0.8)
        self.assertLess(recovered.lm(LM_RIGHT_WRIST)[0], 0.54)

    def test_impossible_forearm_is_rejected(self):
        tracker = PoseTracker()
        raw = pose(left_x=1.6).landmarks
        self.assertIsNone(tracker._derive_metrics(raw, 640, 360).lm(LM_LEFT_WRIST))

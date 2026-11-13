"""Observed-time charge grace and complete fall/count/recovery contracts."""

import unittest
from unittest.mock import patch
import config
from camera.charge import ChargeController
from camera.calibration import CalibrationData
from camera.pose_tracker import PoseData, LM_LEFT_WRIST, LM_RIGHT_WRIST
from core.tracking import TrackingData
from gameplay.player import Player
from gameplay.enemy import Enemy
from gameplay.ai import EnemyAI
from test_punch_boundary import pose


class ChargeGraceTests(unittest.TestCase):
    def setUp(self):
        self.charge = ChargeController()
        self.cal = CalibrationData(torso_height=0.4, arm_length=0.4, punch_direction=1)

    def tick(self, candidate, dt=1 / 30, now=None):
        self.now = getattr(self, "now", 0) + dt if now is None else now
        with patch.object(
            self.charge,
            "candidate",
            side_effect=lambda p, side, c: candidate if side == "left" else False,
        ):
            self.charge.update(None, dt, self.cal, self.now)

    def test_entry_requires_one_hundred_ms(self):
        self.tick(True)
        self.tick(True)
        self.assertFalse(self.charge.active)
        self.tick(True)
        self.assertTrue(self.charge.active)

    def test_brief_missing_landmark_pauses_without_counting_gap(self):
        for _ in range(60):
            self.tick(True)
        progress = self.charge.progress
        for _ in range(5):
            self.tick(None)
        self.assertEqual(self.charge.progress, progress)
        self.assertIn("interrupted", self.charge.hint)
        self.tick(True)
        self.assertEqual(self.charge.progress, progress)
        self.tick(True)
        self.assertGreater(self.charge.progress, progress)

    def test_three_hundred_ms_loss_resets_incomplete_charge(self):
        for _ in range(30):
            self.tick(True)
        for _ in range(10):
            self.tick(None)
        self.assertEqual(self.charge.progress, 0)

    def test_confident_release_has_grace_and_corrective_hint(self):
        for _ in range(30):
            self.tick(True)
        self.tick(False)
        self.assertGreater(self.charge.progress, 0)
        self.assertIn("Bring", self.charge.hint)
        for _ in range(4):
            self.tick(False)
        self.assertEqual(self.charge.progress, 0)

    def test_duplicate_timestamp_cannot_advance_charge(self):
        for _ in range(30):
            self.tick(True)
        before = self.charge.progress
        for _ in range(100):
            self.tick(True, now=self.now)
        self.assertEqual(self.charge.progress, before)

    def test_either_arm_candidate_uses_anatomical_landmarks(self):
        for side in ("left", "right"):
            p = pose(left_x=0.34, wrist_y=0.31)
            if side == "right":
                p.landmarks[LM_RIGHT_WRIST] = p.landmarks[LM_LEFT_WRIST]
            self.assertTrue(self.charge.candidate(p, side, self.cal))

    def test_forward_stretched_arm_cannot_charge(self):
        self.assertFalse(self.charge.candidate(pose(left_x=0.8), "left", self.cal))


class RecoveryTests(unittest.TestCase):
    def test_player_completes_fall_before_accepting_getup(self):
        p = Player()
        p.force_knockdown()
        p.update(0.1, TrackingData(hands_up=True), 0)
        self.assertEqual(p.state, "knockdown")
        p.update(0.4, TrackingData(hands_up=True), 0.5)
        self.assertEqual(p.state, "getup")
        p.ability_ready = True
        origin = p.x
        for i in range(15):
            p.update(
                1 / 30,
                TrackingData(present=True, horizontal_position=0.65, left_punch=True),
                i / 30,
            )
        self.assertEqual(p.state, "getup")
        self.assertEqual(p.x, origin)
        self.assertTrue(p.ability_ready)
        p.update(0.03, TrackingData(), 1)
        self.assertEqual(p.state, "idle")
        self.assertGreater(p.invuln_timer, 1)

    def test_terminal_knockout_never_gets_up(self):
        p = Player()
        p.force_knockdown()
        p.update(11, TrackingData(), 11)
        self.assertEqual(p.state, "ko")
        p.get_up()
        self.assertEqual(p.state, "ko")
        self.assertFalse(p._start_punch("left", 12))

    def test_enemy_recovery_blocks_ai_motion_and_attack(self):
        p = Player(400)
        e = Enemy(config.ENEMIES["jessie"], 800)
        e.force_knockdown()
        with patch("gameplay.enemy.random.random", return_value=0):
            e.update(3, 3)
        self.assertEqual(e.state, "getup")
        origin = e.x
        ai = EnemyAI(e, p)
        ai.update(0.1, False)
        self.assertEqual(e.x, origin)
        self.assertFalse(ai.start_attack())
        self.assertFalse(e.take_hit(100, 0, 1))
        e.update(0.53, 4)
        self.assertEqual(e.state, "idle")

    def test_third_enemy_knockdown_is_terminal(self):
        e = Enemy(config.ENEMIES["jessie"], 800)
        for _ in range(3):
            e.force_knockdown()
        with patch("gameplay.enemy.random.random", return_value=0):
            e.update(10, 10)
        self.assertEqual(e.state, "ko")

    def test_hit_preserves_previous_compatible_pose(self):
        p = Player()
        p.state = "guard"
        p.action_t = 0.2
        p.take_hit(2, 0, 1)
        self.assertEqual(p.hit_pose, ("guard", 0.2))
        self.assertEqual(p.state, "hit")

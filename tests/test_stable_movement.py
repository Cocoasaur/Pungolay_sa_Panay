"""Intent, reacquisition, bounded motion, and body separation regressions."""

import math
import unittest
from types import SimpleNamespace
import config
from camera.movement import MovementController
from camera.pose_tracker import LM_LEFT_HIP, LM_RIGHT_HIP
from core.tracking import TrackingData
from gameplay.player import Player
from gameplay.enemy import Enemy
from gameplay.spacing import separate_fighters


def body(x=0.5, confidence=1, shoulder_offset=0):
    points = {
        LM_LEFT_HIP: (x - 0.04, 0.7, 0, confidence),
        LM_RIGHT_HIP: (x + 0.04, 0.7, 0, confidence),
    }
    return SimpleNamespace(present=True, lm=points.get, body_center_x=x + shoulder_offset)


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.controller = MovementController()
        for _ in range(10):
            self.controller.update(body(), 1 / 30, False)

    def test_stationary_jitter_never_walks_and_drifts_under_two_pixels(self):
        minimum = config.ARENA_MARGIN + config.FIGHTER_BODY_WIDTH / 2
        origin = minimum + 0.35 * (1280 - 2 * minimum)
        player = Player(origin)
        for i in range(300):
            position = self.controller.update(body(0.5 + 0.007 * math.sin(i * 1.7)), 1 / 30, False)
            player.update(
                1 / 30,
                TrackingData(
                    present=True, horizontal_position=position, movement_valid=self.controller.valid
                ),
                i / 30,
            )
            self.assertEqual(player.state, "idle")
            self.assertLessEqual(abs(player.x - origin), 2)

    def test_deliberate_step_begins_within_two_hundred_ms(self):
        for i in range(6):
            self.controller.update(body(0.54), 1 / 30, False)
            if self.controller.state == "MOVING":
                break
        self.assertEqual(self.controller.state, "MOVING")
        self.assertLessEqual((i + 1) / 30, 0.2)
        self.assertGreater(self.controller.position, 0.35)

    def test_below_entry_boundary_holds_last_position(self):
        for _ in range(20):
            self.controller.update(body(0.516), 1 / 30, False)
        self.assertEqual(self.controller.position, 0.35)

    def test_stopping_rebases_dead_zone_around_new_hold(self):
        for _ in range(20):
            self.controller.update(body(0.55), 1 / 30, False)
        held = self.controller.position
        for i in range(90):
            self.controller.update(body(0.55 + 0.006 * math.sin(i)), 1 / 30, False)
        self.assertEqual(self.controller.state, "HOLDING")
        self.assertEqual(self.controller.position, held)

    def test_arm_and_shoulder_turns_do_not_move_hip_anchor(self):
        for i in range(60):
            self.controller.update(body(shoulder_offset=0.2 * math.sin(i)), 1 / 30, False)
        self.assertEqual(self.controller.position, 0.35)

    def test_low_confidence_hips_freeze_and_reacquire_without_jump(self):
        for _ in range(20):
            self.controller.update(body(0.6), 1 / 30, False)
        held = self.controller.position
        self.controller.update(body(0.8, 0.2), 1 / 30, False)
        self.assertFalse(self.controller.valid)
        for _ in range(6):
            self.controller.update(body(0.72), 1 / 30, False)
        self.assertTrue(self.controller.valid)
        self.assertEqual(self.controller.position, held)

    def test_missing_hips_are_not_replaced_with_shoulders(self):
        self.controller.update(SimpleNamespace(present=True, lm=lambda i: None), 1 / 30, False)
        self.assertEqual(self.controller.state, "TRACKING LOST")

    def test_single_outlier_cannot_move_character(self):
        self.controller.update(body(0.98), 1 / 30, False)
        self.assertFalse(self.controller.valid)
        for _ in range(12):
            self.controller.update(body(), 1 / 30, False)
        self.assertEqual(self.controller.position, 0.35)

    def test_recenter_changes_anchor_without_changing_position(self):
        self.controller.recenter(0.42)
        for _ in range(10):
            self.controller.update(body(0.7), 1 / 30, False)
        self.assertEqual(self.controller.position, 0.42)

    def test_mirror_reverses_movement_without_swapping_hips(self):
        other = MovementController()
        for _ in range(10):
            other.update(body(), 1 / 30, True)
        for _ in range(20):
            other.update(body(0.55), 1 / 30, True)
            self.controller.update(body(0.55), 1 / 30, False)
        self.assertAlmostEqual(other.position - 0.35, -(self.controller.position - 0.35))

    def test_physical_speed_acceleration_and_size_are_bounded(self):
        player = Player(400)
        last_speed = 0
        for i in range(180):
            before = player.x
            player.update(
                1 / 60, TrackingData(present=True, horizontal_position=0.65, player_scale=2), i / 60
            )
            speed = (player.x - before) * 60
            self.assertLessEqual(abs(speed), player.move_speed + 1e-6)
            # Stopping at the target may clamp speed immediately.
            if speed > last_speed:
                self.assertLessEqual(speed - last_speed, player.move_speed / 0.15 / 60 + 1e-6)
            self.assertEqual(player.scale, 1)
            last_speed = speed
        self.assertEqual(player.state, "idle")

    def test_stale_input_freezes_immediately(self):
        player = Player(400)
        data = TrackingData(present=True, horizontal_position=0.65)
        player.update(0.05, data, 0)
        before = player.x
        player.update(
            0.05, TrackingData(present=True, movement_valid=False, horizontal_position=0.65), 0.05
        )
        self.assertEqual(player.x, before)


class SpacingTests(unittest.TestCase):
    def test_overlap_crossing_and_walls_preserve_body_gap(self):
        for px, ex in [(500, 500), (900, 200), (-400, -300), (1400, 1500), (1200, 1250), (20, 30)]:
            player = Player(px)
            enemy = Enemy(config.ENEMIES["jessie"], ex)
            separate_fighters(player, enemy)
            self.assertGreaterEqual(enemy.x - player.x, (player.body_w + enemy.body_w) / 2 + 8)
            self.assertGreaterEqual(player.x - player.body_w / 2, config.ARENA_MARGIN)
            self.assertLessEqual(enemy.x + enemy.body_w / 2, 1280 - config.ARENA_MARGIN)

    def test_hitboxes_follow_collision_correction(self):
        player = Player(600)
        enemy = Enemy(config.ENEMIES["jessie"], 610)
        player._start_punch("left", 0)
        player._update_punch(0.1)
        offset = player.active_hitbox.x - player.x
        separate_fighters(player, enemy)
        self.assertAlmostEqual(player.active_hitbox.x - player.x, offset)

    def test_collision_blocked_player_returns_to_idle(self):
        player = Player(500)
        enemy = Enemy(config.ENEMIES["jessie"], 600)
        for i in range(60):
            before = player.x
            player.update(
                1 / 60,
                TrackingData(present=True, horizontal_position=0.65),
                i / 60,
                defer_motion=True,
            )
            separate_fighters(player, enemy)
            player.finalize_motion(1 / 60, before)
        # At the right wall both fighters stop despite a continuing target.
        for i in range(180):
            before = player.x
            player.update(
                1 / 60, TrackingData(present=True, horizontal_position=1), i / 60, defer_motion=True
            )
            separate_fighters(player, enemy)
            player.finalize_motion(1 / 60, before)
        self.assertEqual(player.state, "idle")

    def test_enemy_approach_does_not_shove_stationary_player_or_start_walking(self):
        player = Player(500)
        enemy = Enemy(config.ENEMIES["jessie"], 600)
        separate_fighters(player, enemy)
        origin = player.x
        for _ in range(30):
            px, ex = player.x, enemy.x
            enemy.x -= 4
            separate_fighters(player, enemy, px, ex)
            player.finalize_motion(1 / 30, px)
        self.assertAlmostEqual(player.x, origin)
        self.assertEqual(player.state, "idle")

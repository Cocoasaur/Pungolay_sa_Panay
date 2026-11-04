"""Accepted attacks own their damage and readiness; animation stays grounded."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
import config
from camera.calibration import CalibrationData
from camera.gesture_detector import GestureDetector
from core.input_controller import KeyboardInput
from core.tracking import TrackingData
from gameplay.player import Player
from gameplay.enemy import Enemy
from gameplay.ai import EnemyAI
from test_punch_boundary import pose


class ChargeTests(unittest.TestCase):
    def test_charge_completes_once_at_five_seconds_and_survives_pose_exit(self):
        detector = GestureDetector()
        cal = CalibrationData(torso_height=0.4, arm_length=0.4, punch_direction=1)
        tucked = pose(left_x=0.34, wrist_y=0.31)
        edges = []
        for i in range(110):
            detector.update(tucked, 0.05, cal, now=(i + 1) * 0.05)
            if detector.charge_completed:
                edges.append(i)
        self.assertEqual(len(edges), 1)
        self.assertIn(edges[0], (99, 100))
        player = Player()
        player.update(0.016, TrackingData(charge_completed=True), 0)
        detector.update(pose(), 0.05, cal, now=6)
        player.update(0.016, TrackingData(), 6)
        self.assertTrue(player.ability_ready)

    def test_next_accepted_punch_from_either_arm_spends_charge_even_on_miss(self):
        for side in ("left", "right"):
            player = Player()
            player.ability_ready = True
            self.assertTrue(player._start_punch(side, 0))
            self.assertFalse(player.ability_ready)
            self.assertEqual(player.accepted_attack.side, side)
            player._update_punch(0.10)
            self.assertEqual(player.active_hitbox.damage, player.punch_damage * 2)
            self.assertEqual(player.active_hitbox.attack_type, "HAYMAKER")
            player._update_punch(1)
            player._punch_cooldown = 0
            self.assertTrue(player._start_punch(side, 2))
            player._update_punch(0.10)
            self.assertEqual(player.active_hitbox.damage, player.punch_damage)
            self.assertEqual(player.active_hitbox.attack_type, "NORMAL")

    def test_rejected_inputs_and_hits_do_not_spend_readiness(self):
        for state in ("hit", "punch_l", "knockdown", "ko"):
            player = Player()
            player.ability_ready = True
            player.state = state
            self.assertFalse(player._start_punch("right", 0))
            self.assertTrue(player.ability_ready)
        player = Player()
        player.ability_ready = True
        player._punch_cooldown = 0.4
        self.assertFalse(player._start_punch("left", 0))
        self.assertTrue(player.ability_ready)
        player.take_hit(1, 0, 1)
        self.assertTrue(player.ability_ready)

    def test_legacy_haymaker_input_cannot_mint_a_free_charge(self):
        player = Player()
        player._start_punch("left", 0, True)
        player._update_punch(0.1)
        self.assertEqual(player.active_hitbox.attack_type, "NORMAL")

    def test_attack_snapshot_does_not_change_during_windup(self):
        player = Player()
        player.ability_ready = True
        player._start_punch("left", 0)
        original = player.accepted_attack.damage
        player.punch_damage = 999
        player._update_punch(0.1)
        self.assertEqual(player.active_hitbox.damage, original)

    def test_sustained_block_does_not_alternate_with_idle(self):
        player = Player()
        player.ability_ready = True
        for i in range(120):
            player.update(1 / 60, TrackingData(guard=True), i / 60)
            self.assertTrue(player.guarding)
            self.assertEqual(player.state, "guard")
        self.assertTrue(player.ability_ready)
        player.update(0.016, TrackingData(), 3)
        self.assertEqual(player.state, "idle")

    def test_stationary_player_returns_to_idle(self):
        player = Player()
        data = TrackingData(present=True, horizontal_position=0.2)
        player.update(0.016, data, 0)
        self.assertEqual(player.state, "walk")
        for i in range(30):
            player.update(0.016, data, i * 0.016)
        self.assertEqual(player.state, "idle")
        self.assertEqual(player.motion_direction, 0)

    def test_enemy_extension_has_a_defined_active_duration(self):
        enemy = Enemy(config.ENEMIES["jessie"], 800)
        enemy.state = "windup"
        enemy.state_timer = 0.01
        enemy.update(0.016, 0)
        self.assertEqual(enemy.state, "attack")
        self.assertIsNotNone(enemy.active_hitbox)
        enemy.update(0.05, 0.05)
        self.assertEqual(enemy.state, "attack")
        enemy.update(0.12, 0.17)
        self.assertEqual(enemy.state, "recover")
        self.assertIsNone(enemy.active_hitbox)

    def test_enemy_stopped_by_arena_edge_returns_to_idle(self):
        enemy = Enemy(config.ENEMIES["jessie"], config.BASE_WIDTH)
        player = Player(100)
        enemy.state = "retreat"
        ai = EnemyAI(enemy, player)
        ai._apply_movement(0.016)
        ai._apply_movement(0.016)
        self.assertEqual(enemy.state, "idle")
        self.assertEqual(enemy.facing, -1)


class KeyboardChargeTests(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        pygame.quit()

    def test_completed_hold_release_does_not_attack_next_tap_does(self):
        keyboard = KeyboardInput()
        held = {"j"}

        class Keys:
            def __getitem__(self, key):
                return pygame.key.name(key) in held

        with patch("core.input_controller.pygame.key.get_pressed", return_value=Keys()):
            events = [keyboard.update(0.1) for _ in range(60)]
            self.assertEqual(sum(t.charge_completed for t in events), 1)
            held.clear()
            keyboard.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_j))
            self.assertFalse(keyboard.update(0.016).left_punch)
            held.add("k")
            keyboard.update(0.05)
            held.clear()
            keyboard.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_k))
            self.assertTrue(keyboard.update(0.016).right_punch)

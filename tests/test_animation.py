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
from ui.animation import draw_animation, prewarm_pair
from ui.animation_cache import cache
from test_punch_boundary import pose


class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        for fighter in ["player", *config.OPPONENT_ORDER]:
            prewarm_pair((fighter, 1))
        assert cache.wait_ready(30)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_manifest_has_all_eight_fighters_and_232_frames(self):
        data = json.loads((Path(config.SPRITES_DIR) / "animations.json").read_text())
        self.assertEqual(set(data["fighters"]), {"player", *config.OPPONENT_ORDER})
        total = 0
        for fighter in data["fighters"].values():
            self.assertEqual(len(fighter["clips"]), 9)
            for clip in fighter["clips"].values():
                image = pygame.image.load(str(Path(config.SPRITES_DIR) / clip["sheet"]))
                self.assertTrue(image.get_flags() & pygame.SRCALPHA)
                for frame in clip["frames"]:
                    self.assertTrue(image.get_rect().contains(frame["rect"]))
                    self.assertTrue(all(0 < v < 1 for v in frame["pivot"]))
                total += len(clip["frames"])
        self.assertEqual(total, 232)

    def test_all_frames_keep_soles_grounded_and_do_not_clip(self):
        for fighter in ["player", *config.OPPONENT_ORDER]:
            for state, times in [
                ("punch_l", (0.02, 0.10, 0.3)),
                ("punch_r", (0.02, 0.10, 0.3)),
                ("guard", (0.02, 0.2)),
                ("walk", (0.02, 0.15, 0.27, 0.4)),
            ]:
                for charged in (False, True) if state.startswith("punch") else (False,):
                    for t in times:
                        canvas = pygame.Surface((600, 600), pygame.SRCALPHA)
                        self.assertTrue(
                            draw_animation(
                                canvas, fighter, state, t, 300, 500, 1, 1, charged=charged
                            )
                        )
                        bounds = canvas.get_bounding_rect(min_alpha=150)
                        self.assertLessEqual(
                            abs(bounds.bottom - 500), 2, (fighter, state, t, bounds)
                        )
                        self.assertGreater(bounds.left, 0)
                        self.assertLess(bounds.right, 600)
                        self.assertGreater(bounds.top, 0)

    def test_punch_frames_match_windup_active_and_recovery(self):
        images = []
        for t in (0.02, 0.1, 0.3):
            canvas = pygame.Surface((600, 600), pygame.SRCALPHA)
            draw_animation(canvas, "player", "punch_l", t, 300, 500, 1, 1)
            images.append(pygame.image.tobytes(canvas, "RGBA"))
        self.assertEqual(len(set(images)), 3)

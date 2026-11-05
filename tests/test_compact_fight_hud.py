"""Arena visibility, readable combat cues, and compact camera input geometry."""

import unittest
from unittest.mock import patch

import numpy as np
import pygame
import config
from core.tracking import TrackingData
from ui.hud import HUD
from ui import theme
from ui.fonts import load_fonts
import test_game_startup as startup


class CompactFightHUDTests(unittest.TestCase):
    setUp = startup.GameStartupTests.setUp

    def fight(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.start_new_game()
        fight = self.game.states.current
        fight.intro_timer = 0
        fight.tutorial.active = False
        return fight

    def test_idle_hud_leaves_over_92_percent_of_arena_pixels_untouched(self):
        fight = self.fight()
        background = (89, 131, 167)
        canvas = pygame.Surface((1280, 720))
        canvas.fill(background)
        fight.hud.draw(canvas, fight.player, fight.enemy, camera_status="KEYBOARD MODE")
        pixels = pygame.surfarray.array3d(canvas)
        unchanged = np.all(pixels == background, axis=2)
        self.assertGreater(unchanged.mean(), 0.92)
        self.assertTrue(unchanged[:, 86:128].all())
        self.assertTrue(unchanged[324:956, :86].all())
        self.assertEqual(config.FIGHTER_BODY_HEIGHT, 240)
        self.assertEqual(config.GROUND_Y, 620)

    def test_camera_and_hud_leave_over_90_percent_of_arena_pixels_untouched(self):
        fight = self.fight()
        self.game.settings["input_mode"] = "camera"
        self.game.last_camera_frame = np.zeros((360, 640, 3), np.uint8)
        self.game.last_pose = None
        canvas = pygame.Surface((1280, 720))
        canvas.fill((89, 131, 167))
        fight.hud.draw(canvas, fight.player, fight.enemy, tracking=TrackingData())
        fight._draw_camera_preview(canvas)
        unchanged = np.all(pygame.surfarray.array3d(canvas) == (89, 131, 167), axis=2)
        self.assertGreater(unchanged.mean(), 0.90)

    def test_keyboard_charge_instructions_follow_input_and_readiness(self):
        fight = self.fight()
        for active, ready, expected in (
            (False, False, "Hold J or K for 5s, then tap either to punch"),
            (True, False, "Keep holding J or K; release when ready"),
            (False, True, "Tap J or K to use"),
        ):
            fight.player.ability_ready = ready
            with patch.object(fight.hud, "_label", wraps=fight.hud._label) as labels:
                fight.hud.draw(
                    self.game.canvas,
                    fight.player,
                    fight.enemy,
                    camera_status="KEYBOARD MODE",
                    tracking=TrackingData(is_charging=active),
                )
                self.assertIn(expected, [c.args[1] for c in labels.call_args_list])

    def test_health_fill_and_stamina_still_reflect_gameplay_values(self):
        fight = self.fight()
        fight.player.hp = fight.player.max_hp * 0.5
        fight.player.stamina = 0
        canvas = pygame.Surface((1280, 720))
        fight.hud.draw(canvas, fight.player, fight.enemy)
        self.assertEqual(canvas.get_at((100, 53))[:3], config.COLORS["hp_red"])
        self.assertEqual(canvas.get_at((200, 53))[:3], (60, 49, 38))
        self.assertEqual(canvas.get_at((150, 74))[:3], (60, 49, 38))

    def test_haymaker_progress_both_arms_and_authoritative_readiness(self):
        fight = self.fight()
        canvas = pygame.Surface((1280, 720))
        for side, color in (("left", config.ARM_LEFT_COLOR), ("right", config.ARM_RIGHT_COLOR)):
            data = TrackingData(is_charging=True, charge_progress=0.6, charge_side=side)
            with patch.object(fight.hud, "_label", wraps=fight.hud._label) as labels:
                fight.hud.charge(canvas, fight.player, data)
                self.assertIn(
                    f"{side.upper()} HAYMAKER / 2.0s", [c.args[1] for c in labels.call_args_list]
                )
            self.assertEqual(canvas.get_at((500, 695))[:3], color)
            self.assertEqual(canvas.get_at((820, 695))[:3], (60, 49, 38))
        fight.player.ability_ready = True
        # An empty fresh camera sample must never hide stored readiness.
        with patch.object(fight.hud, "_label", wraps=fight.hud._label) as labels:
            fight.hud.charge(canvas, fight.player, TrackingData())
            self.assertIn(
                "HAYMAKER READY / NEXT PUNCH 2×", [c.args[1] for c in labels.call_args_list]
            )
        self.assertEqual(canvas.get_at((820, 695))[:3], config.COLORS["warm_glow"])

    def test_only_actionable_tracking_status_occupies_warning_area(self):
        fight = self.fight()
        for status in ("HOLDING", "MOVING"):
            self.assertIsNone(
                HUD.tracking_warning("CAMERA", False, TrackingData(movement_status=status))
            )
        self.assertIsNone(
            HUD.tracking_warning(
                "KEYBOARD MODE", True, TrackingData(movement_status="TRACKING LOST")
            )
        )
        warning = HUD.tracking_warning(
            "CAMERA", False, TrackingData(movement_status="TRACKING LOST", pose_present=True)
        )
        self.assertIn("Show both hips", warning[1])
        self.assertFalse(HUD.WARNING.colliderect(HUD.CHARGE))
        self.assertGreater(HUD.CHARGE.top, config.GROUND_Y)
        self.assertGreater(HUD.WARNING.top, config.GROUND_Y)

    def test_all_hud_text_fits_in_bundled_and_fallback_fonts(self):
        fight = self.fight()
        canvas = pygame.Surface((1280, 720))
        for fontdir in (config.FONTS_DIR, "/tmp/no-fonts-here"):
            with patch.object(config, "FONTS_DIR", fontdir):
                theme.fitted.cache_clear()
                fight.hud.fonts = load_fonts()
                with patch.object(fight.hud, "_label", wraps=fight.hud._label) as labels:
                    for enemy in config.ENEMIES.values():
                        fight.enemy.name, fight.enemy.title = enemy["name"], enemy["title"]
                        for data, ready in (
                            (TrackingData(), False),
                            (
                                TrackingData(
                                    is_charging=True, charge_side="right", charge_progress=0.5
                                ),
                                False,
                            ),
                            (TrackingData(), True),
                        ):
                            fight.player.ability_ready = ready
                            fight.hud.draw(canvas, fight.player, fight.enemy, tracking=data)
                    for call in labels.call_args_list:
                        _, text, pos, width, size, *rest = call.args
                        bold = rest[1] if len(rest) > 1 else call.kwargs.get("bold", False)
                        image = theme.fitted(text, width, size, bold).render(
                            text, True, (255, 255, 255)
                        )
                        self.assertLessEqual(image.get_width(), width, text)
                        self.assertTrue(
                            canvas.get_rect().contains(image.get_rect(topleft=pos)), text
                        )
        theme.fitted.cache_clear()

    def test_camera_toolbar_remains_clickable_when_preview_is_collapsed(self):
        fight = self.fight()
        self.game.settings["input_mode"] = "camera"
        self.game.last_camera_frame = np.zeros((360, 640, 3), np.uint8)
        self.game.last_pose = None
        for visible in (True, False):
            self.game.settings["camera_preview"] = visible
            canvas = pygame.Surface((1280, 720))
            canvas.fill((89, 131, 167))
            fight._draw_camera_preview(canvas)
            self.assertTrue(canvas.get_rect().contains(fight.preview_toggle_rect))
            self.assertTrue(canvas.get_rect().contains(fight.recenter_rect))
            self.assertFalse(fight.recenter_rect.colliderect(fight.preview_toggle_rect))
            if not visible:
                self.assertEqual(canvas.get_at((30, 160))[:3], (89, 131, 167))
            with patch.object(self.game, "apply_settings_changes"), patch.object(
                self.game, "recenter_movement"
            ) as recenter:
                fight.handle_event(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1, pos=fight.recenter_rect.center
                    )
                )
                recenter.assert_called_once()
                fight.handle_event(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1, pos=fight.preview_toggle_rect.center
                    )
                )
                self.assertEqual(self.game.settings["camera_preview"], not visible)
        self.game.settings["input_mode"] = "keyboard"
        with patch.object(self.game, "recenter_movement") as recenter:
            fight.handle_event(
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=fight.recenter_rect.center)
            )
            recenter.assert_not_called()

    def test_tutorial_shows_next_objective_and_keeps_completed_steps_out_of_view(self):
        fight = self.fight()
        fight.tutorial.start()
        fight.tutorial._checks[0]["done"] = True
        with patch.object(fight.hud, "_label", wraps=fight.hud._label) as labels:
            fight._draw_tutorial(self.game.canvas)
            self.assertEqual(
                [c.args[1] for c in labels.call_args_list],
                ["PRACTICE / 1 OF 5", "Move left & right"],
            )
        self.assertFalse(HUD.HEALTH_LEFT.colliderect(pygame.Rect(448, 18, 384, 58)))
        self.assertFalse(HUD.HEALTH_RIGHT.colliderect(pygame.Rect(448, 18, 384, 58)))

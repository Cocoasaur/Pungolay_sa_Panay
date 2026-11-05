"""Contained typography, fresh-only camera artwork, and unblocked charge cues."""

import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pygame
import config
from core.tracking import TrackingData
from ui.main_menu import MainMenu
from ui.settings import SettingsScene
from ui.screens import CameraDebugView, CalibrationScreen
from ui.animation_cache import AnimationCache, cache
from ui.animation import prewarm_pair, draw_animation
from ui import theme
import test_game_startup as startup


class PosterTests(unittest.TestCase):
    setUp = startup.GameStartupTests.setUp

    def test_title_and_actions_fit_with_bundled_and_fallback_fonts(self):
        for fontdir in (config.FONTS_DIR, "/tmp/no-fonts-here"):
            with patch.object(config, "FONTS_DIR", fontdir):
                theme.fitted.cache_clear()
                menu = MainMenu(self.game)
                for image, pos in [(menu.title_surf, (96, 100)), (menu.subtitle_surf, (96, 142))]:
                    self.assertTrue(menu.title_bounds.contains(image.get_rect(topleft=pos)))
                for rect in menu._item_rects:
                    self.assertTrue(menu.panel_rect.contains(rect))
        theme.fitted.cache_clear()

    def test_deprecated_distance_and_smoothing_values_remain_saved_but_hidden(self):
        scene = SettingsScene(self.game)
        for tab in range(3):
            scene.tab = tab
            scene._build_rows()
            self.assertFalse(
                {"smoothing", "distance_sensitivity"} & {row["key"] for row in scene._rows}
            )
        self.assertIn("distance_sensitivity", self.game.settings)

    def test_preview_toggle_and_recenter_preserve_world_position_and_calibration(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.start_new_game()
        fight = self.game.states.current
        fight.player.x = 410
        cal = dict(self.game.settings.get("calibration") or {})
        fight.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F4))
        self.assertFalse(self.game.settings["camera_preview"])
        fight.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.assertEqual(fight.player.x, 410)
        self.assertEqual(dict(self.game.settings.get("calibration") or {}), cal)

    def test_hitstop_updates_charge_cues_and_completion(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.start_new_game()
        fight = self.game.states.current
        fight.intro_timer = 0
        fight.combat.hitstop = 0.1
        data = TrackingData(is_charging=True, charge_progress=0.6, charge_side="left")
        with patch.object(self.game, "get_current_tracking", return_value=data):
            fight.update(0.016)
        self.assertEqual(fight.player.charge_progress, 0.6)
        self.assertTrue(fight.player.is_charging)
        data.charge_completed = True
        data.charge_progress = 1
        with patch.object(self.game, "get_current_tracking", return_value=data):
            fight.update(0.016)
        self.assertTrue(fight.player.ability_ready)

    def test_pause_never_polls_or_advances_charge(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.start_new_game()
        fight = self.game.states.current
        fight.player.charge_progress = 0.6
        self.game.states.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        with patch.object(self.game, "get_current_tracking") as poll:
            self.game.states.update(1)
            poll.assert_not_called()
        self.assertEqual(fight.player.charge_progress, 0.6)

    def test_debug_and_practice_rebuild_overlay_only_when_sample_or_options_change(self):
        for cls in (CameraDebugView, CalibrationScreen):
            scene = cls(self.game)
            self.game.last_camera_frame = np.zeros((360, 640, 3), np.uint8)
            pose = SimpleNamespace(present=False)
            self.game.tracking = TrackingData(sample_id=1)
            with patch.object(
                self.game, "poll_camera_for_calibration", return_value=(self.game.tracking, pose)
            ), patch.object(
                self.game.pose_tracker, "draw_debug_frame", side_effect=lambda frame, *a, **k: frame
            ) as draw, patch.object(
                self.game.gestures, "draw_punch_boundary", side_effect=lambda frame, *a, **k: frame
            ):
                for _ in range(5):
                    scene.update(0.016)
                self.assertEqual(draw.call_count, 1)
                self.game.raw_landmarks = not self.game.raw_landmarks
                scene.update(0.016)
                self.assertEqual(draw.call_count, 2)

    def test_terminal_ko_holds_identical_final_frame(self):
        prewarm_pair(("player", 1))
        self.assertTrue(cache.wait_ready(20))
        frames = []
        for t in (0.5, 5, 20):
            canvas = pygame.Surface((600, 600), pygame.SRCALPHA)
            self.assertTrue(draw_animation(canvas, "player", "ko", t, 300, 500, 1, 1))
            frames.append(pygame.image.tobytes(canvas, "RGBA"))
        self.assertEqual(len(set(frames)), 1)

    def test_cache_cancel_ignores_old_generation_and_stays_under_budget(self):
        prewarm_pair(("player", 1))
        cache.cancel()
        prewarm_pair(("player", 1))
        self.assertTrue(cache.wait_ready(30))
        self.assertFalse(cache.pending)
        self.assertLessEqual(cache.memory_bytes, config.ANIMATION_CACHE_BYTES)

    def test_missing_knockout_art_uses_downed_procedural_pose_before_standing_png(self):
        from ui.sprites import draw_boxer
        canvas=pygame.Surface((600,600),pygame.SRCALPHA)
        with patch('ui.sprites.draw_animation',return_value=False),patch('ui.sprites._sprite_path') as standing:
            draw_boxer(canvas,300,500,1,'ko',10,1,(30,30,30))
            standing.assert_not_called()
        self.assertLess(canvas.get_bounding_rect().height,130)

    def test_new_clips_are_grounded_mirrored_and_share_neutral_height(self):
        from pathlib import Path
        from ui.animation import manifest
        data=manifest(str(Path(config.SPRITES_DIR)/'animations.json'))
        for name,fighter in data['fighters'].items():
            prewarm_pair((name,1),(name,-1));self.assertTrue(cache.wait_ready(20))
            for state,times in [('idle',(.05,.45,.85,1.25)),('knockdown',(.02,.15,.3,.46)),('getup',(.02,.2,.4))]:
                clip=fighter['clips'][state]
                self.assertEqual(clip.get('loop',False),state=='idle')
                for frame in clip['frames']:
                    image=pygame.image.load(str(Path(config.SPRITES_DIR)/clip['sheet']))
                    x,y,w,h=frame['rect'];cell=image.subsurface((x,y,w,h))
                    bounds=cell.get_bounding_rect(min_alpha=150)
                    self.assertGreater(bounds.left,0);self.assertGreater(bounds.top,0)
                    self.assertLess(bounds.right,w);self.assertLess(bounds.bottom,h)
                for t in times:
                    for facing in (1,-1):
                        canvas=pygame.Surface((700,600),pygame.SRCALPHA)
                        self.assertTrue(draw_animation(canvas,name,state,t,350,500,1,facing))
                        bounds=canvas.get_bounding_rect(min_alpha=150)
                        self.assertLessEqual(abs(bounds.bottom-500),2,(name,state,t,facing,bounds))
                        if state=='idle':self.assertLessEqual(abs(bounds.height-240),5,(name,bounds))

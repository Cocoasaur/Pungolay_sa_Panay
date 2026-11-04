"""Headless checks for startup, screen rendering, and camera integration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, create_autospec, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import config
from camera.camera_manager import CameraManager
from camera.pose_tracker import PoseData
from core.game import Game
from ui.screens import CameraErrorScreen, DefeatScreen, VictoryScreen


class GameStartupTests(unittest.TestCase):
    def setUp(self):
        drivers = patch.dict(os.environ, {
            "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
        })
        drivers.start()
        self.addCleanup(drivers.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name, value in {
            "SAVES_DIR": temp.name,
            "SETTINGS_PATH": str(Path(temp.name) / "settings.json"),
        }.items():
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        audio = patch("core.game.AudioManager")
        audio.start()
        self.addCleanup(audio.stop)
        self.game = Game()
        self.addCleanup(self.game.shutdown)

    def test_startup_renders_menu_debug_overlay_and_exits(self):
        self.assertIs(self.game.camera.pose_tracker, self.game.pose_tracker)
        self.assertEqual(self.game.states.current.name, "main_menu")
        self.game.debug_overlay = True
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        self.game.run()
        self.assertFalse(self.game.running)

    def test_keyboard_fight_updates_and_renders(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.apply_settings_changes()
        self.game.start_new_game()
        self.assertEqual(self.game.states.current.name, "gameplay")
        self.game.states.update(self.game.dt)
        self.game.states.draw(self.game.canvas)

    def test_fight_after_calibration_draws_all_debug_body_hitboxes(self):
        self.game.settings["input_mode"] = "camera"
        self.game.debug_overlay = True
        with patch.object(self.game, "_ensure_camera", return_value=True), patch.object(
                self.game.camera, "read_latest", return_value=(False, None, None)):
            self.game.start_calibration()
            self.game.on_calibration_done()
            scene = self.game.states.current
            self.assertEqual(scene.name, "gameplay")
            self.game.states.update(self.game.dt)
            with patch.object(scene, "_draw_hitbox", wraps=scene._draw_hitbox) as draw:
                self.game.states.draw(self.game.canvas)
                expected = [call(self.game.canvas, hitbox, color, 1)
                            for fighter, color in (
                                (scene.player, (120, 120, 255)),
                                (scene.enemy, (255, 120, 255)))
                            for hitbox in fighter.body_hitboxes]
                self.assertEqual(draw.call_args_list, expected)
            self.game._draw_debug_overlay()

    def test_result_and_camera_error_screens_render(self):
        for screen_type in (VictoryScreen, DefeatScreen, CameraErrorScreen):
            with self.subTest(screen=screen_type.__name__):
                screen = screen_type(self.game)
                screen.enter()
                screen.draw(self.game.canvas)
                self.assertTrue(screen._rects)

    def test_campaign_art_and_other_screen_overlays_render(self):
        from ui.pause_menu import PauseMenu
        from ui.screens import (CalibrationScreen, CameraDebugView,
                                LevelSelectScreen, LoadGameScreen)
        from ui.settings import SettingsScene

        self.game.settings["input_mode"] = "keyboard"
        self.game.apply_settings_changes()
        for index in range(len(config.OPPONENT_ORDER)):
            self.game.progression.start_fight(index)
            self.game._enter_fight()
            fight = self.game.states.current
            for state in ("idle", "punch_l", "guard", "hit", "knockdown", "ko"):
                with self.subTest(opponent=index, state=state):
                    fight.player.state = state
                    fight.enemy.state = state
                    fight.draw(self.game.canvas)
            PauseMenu(self.game).draw(self.game.canvas)
            self.game.states.clear()
        for screen_type in (CalibrationScreen, CameraDebugView,
                            LevelSelectScreen, LoadGameScreen):
            with self.subTest(screen=screen_type.__name__):
                screen = screen_type(self.game)
                screen.draw(self.game.canvas)
        with patch("ui.settings.probe_cameras", return_value=[]):
            SettingsScene(self.game).draw(self.game.canvas)

    def test_victory_names_finished_opponent_and_keeps_next_fight_available(self):
        self.game.settings["input_mode"] = "keyboard"
        last = len(config.OPPONENT_ORDER) - 1
        for index, opponent_id in enumerate(config.OPPONENT_ORDER):
            with self.subTest(opponent=opponent_id):
                self.game.states.clear()
                self.game.progression.start_fight(index)
                self.game._enter_fight()
                fight = self.game.states.current
                defeated_name = fight.enemy.name
                fight.combat.winner = "player"
                fight._finish_fight()

                result = self.game.states.current
                self.assertIsInstance(result, VictoryScreen)
                self.assertEqual(result.enemy_name, defeated_name)
                self.assertEqual(result.is_final, index == last)
                self.assertEqual(self.game.progression.current_opponent, min(index + 1, last))
                saved = self.game.save_manager.load_slot(1)
                self.assertEqual(saved["current_opponent"], min(index + 1, last))
                self.assertIn(opponent_id, saved["defeated"])
                result.draw(self.game.canvas)
                result._activate()
                if index == last:
                    self.assertEqual(self.game.states.current.name, "main_menu")
                else:
                    self.assertEqual(self.game.states.current.name, "gameplay")
                    next_name = config.ENEMIES[config.OPPONENT_ORDER[index + 1]]["name"]
                    self.assertEqual(self.game.states.current.enemy.name, next_name)

    def test_calibration_uses_background_pose_and_initializes_tracker(self):
        camera = create_autospec(CameraManager, instance=True)
        camera._cap = None
        camera.status = "UNINITIALIZED"
        camera.open.return_value = True
        pose = PoseData(present=False)
        frame = object()
        camera.read_latest.return_value = (True, frame, pose)
        with patch.object(self.game, "camera", camera), patch.object(
                self.game.pose_tracker, "initialize") as initialize, patch.object(
                self.game.pose_tracker, "process") as process:
            tracking, latest_pose = self.game.poll_camera_for_calibration()
            initialize.assert_called_once_with()
            camera.read_latest.assert_called_once_with()
            process.assert_not_called()
            self.assertIs(latest_pose, pose)
            self.assertIs(self.game.last_camera_frame, frame)
            self.assertFalse(tracking.present)

    def test_calibration_returns_no_pose_when_camera_cannot_open(self):
        with patch.object(self.game.camera, "open", return_value=False), patch.object(
                self.game.camera, "read_latest") as read:
            self.assertEqual(self.game.poll_camera_for_calibration(), (None, None))
            read.assert_not_called()

    def camera_that_connects_on_open(self):
        camera = create_autospec(CameraManager, instance=True)
        camera._cap = None
        camera.status = "UNINITIALIZED"
        camera.read_latest.return_value = (True, None, PoseData(present=False))

        def connect(index):
            camera._cap = object()
            camera.status = "CONNECTED"
            return True

        camera.open.side_effect = connect
        return camera

    def test_camera_debug_initializes_tracker_for_already_open_camera(self):
        camera = self.camera_that_connects_on_open()
        with patch.object(self.game, "camera", camera), patch.object(
                self.game.pose_tracker, "initialize") as initialize:
            self.game.show_camera_debug()
            self.game.states.update(self.game.dt)
            self.game.states.update(self.game.dt)
            camera.open.assert_called_once_with(self.game.settings["camera_index"])
            initialize.assert_called_once_with()
            self.assertTrue(self.game._pose_init_started)

    def test_camera_retry_initializes_tracker_for_already_open_camera(self):
        camera = self.camera_that_connects_on_open()
        with patch.object(self.game, "camera", camera), patch.object(
                self.game.pose_tracker, "initialize") as initialize:
            screen = CameraErrorScreen(self.game)
            self.game.states.push(screen)
            screen.selected = 0
            screen._activate()
            self.assertEqual(self.game.states.current.name, "calibration")
            self.game.states.update(self.game.dt)
            self.game.states.update(self.game.dt)
            camera.open.assert_called_once_with(self.game.settings["camera_index"])
            initialize.assert_called_once_with()
            self.assertTrue(self.game._pose_init_started)


if __name__ == "__main__":
    unittest.main()

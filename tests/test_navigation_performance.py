"""Return contexts, bounded scene stacks, settings writes, and slow hardware."""

import threading
import time
import unittest
from unittest.mock import patch
import pygame
import config
import test_game_startup as startup
from core.state_manager import StateManager, Scene
from ui.screens import CalibrationScreen, VictoryScreen
from ui.pause_menu import PauseMenu
from ui.settings import SettingsScene


class NavigationTests(unittest.TestCase):
    setUp = startup.GameStartupTests.setUp

    def keyboard_fight(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.apply_settings_changes()
        self.game.start_new_game()
        return self.game.states.current

    def escape(self):
        self.game.states.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

    def test_pause_settings_debug_escape_preserves_paused_fight(self):
        fight = self.keyboard_fight()
        fight.player.ability_ready = True
        self.escape()
        pause = self.game.states.current
        self.assertIsInstance(pause, PauseMenu)
        self.game.show_settings(back_to="pause")
        settings = self.game.states.current
        with patch.object(self.game.camera, "request_open"):
            self.game.show_camera_debug()
            self.escape()
        self.assertIs(self.game.states.current, settings)
        self.escape()
        self.assertIs(self.game.states.current, pause)
        self.assertTrue(fight.player.ability_ready)
        self.assertEqual(fight.player.state, "idle")

    def test_debug_raw_toggle_does_not_release_camera(self):
        with patch.object(self.game.camera, "request_open"), patch.object(
            self.game.camera, "release_async"
        ) as release:
            self.game.show_camera_debug()
            self.game.states.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
            self.assertTrue(self.game.raw_landmarks)
            release.assert_not_called()

    def test_debug_from_main_returns_to_main(self):
        origin = self.game.states.current
        with patch.object(self.game.camera, "request_open"):
            self.game.show_camera_debug()
            self.escape()
        self.assertIs(self.game.states.current, origin)

    def test_calibration_escape_cancels_and_never_launches_gameplay(self):
        origin = self.game.states.current
        with patch.object(self.game.camera, "request_open"), patch.object(
            self.game.camera, "release_async"
        ) as release:
            self.game.start_calibration()
            self.escape()
            release.assert_called_once_with()
        self.assertIs(self.game.states.current, origin)

    def test_calibration_complete_from_settings_returns_to_settings(self):
        fight = self.keyboard_fight()
        self.escape()
        pause = self.game.states.current
        self.game.show_settings(back_to="pause")
        settings = self.game.states.current
        with patch.object(self.game.camera, "request_open"):
            self.game.start_calibration(from_settings=True)
            self.game.on_calibration_done()
        self.assertIs(self.game.states.current, settings)
        self.escape()
        self.assertIs(self.game.states.current, pause)
        self.assertIn(fight, self.game.states._stack)

    def test_settings_audio_changes_do_not_reopen_camera_and_are_debounced(self):
        with patch.object(self.game.camera, "release_async") as release, patch.object(
            self.game.save_manager, "save_settings"
        ) as save:
            self.game.settings["music_volume"] = 0.2
            self.game.apply_settings_changes()
            self.game.settings["punch_sensitivity"] = 1.5
            self.game.apply_settings_changes()
            release.assert_not_called()
            save.assert_not_called()
            due = self.game.save_manager._settings_due
            with patch("core.save_manager.time.monotonic", return_value=due - 0.01):
                self.game.save_manager.flush_settings()
            save.assert_not_called()
            with patch("core.save_manager.time.monotonic", return_value=due + 0.01):
                self.game.save_manager.flush_settings()
            save.assert_called_once_with()

    def test_settings_controls_and_back_button_fit_canvas_on_every_page(self):
        scene = SettingsScene(self.game)
        with patch.object(self.game.camera, "request_open"):
            for index in range(3):
                scene._switch_tab(index)
                scene.draw(self.game.canvas)
                for rect in scene._rects + scene.tab_rects + [scene.back_rect]:
                    self.assertTrue(self.game.canvas.get_rect().contains(rect))
        row = scene._rows[0]
        scene._set(row, 0.25)
        self.assertEqual(self.game.settings["music_volume"], 0.25)
        scene.selected = 2
        scene._change_value("return")
        self.assertTrue(self.game.settings["fullscreen"])

    def test_slider_supports_click_and_drag_and_stops_on_release(self):
        scene = SettingsScene(self.game)
        scene._switch_tab(2)
        rect = scene._rects[0]
        scene.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(rect.x + 285, rect.centery))
        )
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(rect.x + 585, rect.centery)))
        self.assertEqual(self.game.settings["music_volume"], 1)
        scene.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(rect.x + 585, rect.centery))
        )
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(rect.x + 285, rect.centery)))
        self.assertEqual(self.game.settings["music_volume"], 1)

    def test_retries_replace_fights_and_clear_readiness(self):
        fight = self.keyboard_fight()
        fight.player.ability_ready = True
        for _ in range(5):
            self.game.retry_fight()
        self.assertEqual(len(self.game.states._stack), 1)
        self.assertFalse(self.game.states.current.player.ability_ready)
        self.assertFalse(fight.player.ability_ready)

    def test_final_victory_has_one_main_menu_button(self):
        screen = VictoryScreen(self.game, enemy_name="CALOY", is_final=True)
        screen.draw(self.game.canvas)
        self.assertEqual(len(screen._rects), 1)

    def test_failure_actions_and_cancel_work_without_camera(self):
        with patch.object(self.game.camera, "request_open"):
            self.game.start_calibration()
            screen = self.game.states.current
            self.game.camera.status = "POSE UNAVAILABLE"
            screen.update(0.016)
            screen.draw(self.game.canvas)
            self.assertEqual(screen._phase, "error")
            self.assertIn("KEYBOARD MODE", screen._actions())
            self.assertTrue(all(r.bottom <= 720 for r in screen._rects))
            screen.selected = screen._actions().index("KEYBOARD MODE")
            screen._activate()
        self.assertEqual(self.game.settings["input_mode"], "keyboard")
        self.assertEqual(self.game.states.current.name, "gameplay")

    def test_screens_render_and_navigate_while_camera_open_takes_over_one_second(self):
        started = threading.Event()
        finish = threading.Event()

        class Cap:
            def isOpened(self):
                return False

            def release(self):
                pass

        def slow_open(index):
            started.set()
            finish.wait(1.15)
            return Cap()

        with patch("camera.camera_manager.cv2.VideoCapture", side_effect=slow_open):
            start = time.perf_counter()
            self.game.show_settings()
            self.game.states.draw(self.game.canvas)
            self.assertLess(time.perf_counter() - start, 0.1)
            settings = self.game.states.current
            settings._switch_tab(1)
            self.assertTrue(started.wait(1))
            for _ in range(5):
                start = time.perf_counter()
                self.game.states.update(0.016)
                self.game.states.draw(self.game.canvas)
                self.assertLess(time.perf_counter() - start, 0.1)
            start = time.perf_counter()
            self.escape()
            self.assertLess(time.perf_counter() - start, 0.1)
            self.assertEqual(self.game.states.current.name, "main_menu")
            # Confirm the slow native operation remains alive after navigation.
            self.assertTrue(self.game.camera._open_thread.is_alive())
            time.sleep(1.16)
            finish.set()
            self.game.camera._open_thread.join(1)
            self.assertIsNone(self.game.camera._cap)

    def test_load_and_level_selection_escape_return_to_caller(self):
        origin = self.game.states.current
        self.game.show_load_game()
        self.escape()
        self.assertIs(self.game.states.current, origin)
        self.game.show_level_select()
        self.escape()
        self.assertIs(self.game.states.current, origin)

    def test_opaque_scene_hides_older_scenes_but_pause_keeps_arena(self):
        calls = []

        class Screen(Scene):
            def __init__(self, label, transparent=False):
                self.label = label
                self.transparent = transparent

            def draw(self, surface):
                calls.append(self.label)

        manager = StateManager()
        manager.push(Screen("old"))
        manager.push(Screen("arena"))
        manager.push(Screen("pause", True))
        manager.draw(None)
        self.assertEqual(calls, ["arena", "pause"])
        calls.clear()
        manager.push(Screen("settings"))
        manager.draw(None)
        self.assertEqual(calls, ["settings"])

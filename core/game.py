"""The Game shell: window, state machine, camera/pose pipeline, save system.

This module owns the camera -> TrackingData pipeline and everything the
scenes need. It never touches gameplay internals directly.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

import pygame

import config
from camera.calibration import CalibrationData, Calibrator
from camera.camera_manager import CameraManager
from camera.distance_estimator import DistanceEstimator
from camera.gesture_detector import GestureDetector
from camera.pose_tracker import (LM_LEFT_SHOULDER, LM_LEFT_WRIST,
                                 LM_LEFT_HIP, LM_RIGHT_HIP,
                                 LM_RIGHT_SHOULDER, LM_RIGHT_WRIST,
                                 PoseData, PoseTracker)
from core.audio import AudioManager
from core.events import EventBus
from core.input_controller import KeyboardInput
from core.save_manager import SaveManager
from core.state_manager import StateManager
from core.tracking import TrackingData
from gameplay.progression import Progression
from levels.level_manager import LevelManager
from ui.fonts import load_fonts

log = logging.getLogger(__name__)


class Game:
    def __init__(self) -> None:
        # ------------------------------------------------------------------
        # pygame shell
        # ------------------------------------------------------------------
        pygame.init()
        pygame.display.set_caption(f"{config.GAME_TITLE} v{config.VERSION}")
        self.canvas = pygame.Surface((config.BASE_WIDTH, config.BASE_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.fps = 0.0

        # ------------------------------------------------------------------
        # services
        # ------------------------------------------------------------------
        self.save_manager = SaveManager()
        self.settings = self.save_manager.settings
        self.fonts = load_fonts()
        self.audio = AudioManager()
        self.events = EventBus()
        self._wire_audio_events()

        self.states = StateManager()
        self.progression = Progression()
        self.level_manager = LevelManager(self.progression)

        # ------------------------------------------------------------------
        # camera / vision pipeline
        # ------------------------------------------------------------------
        backend = self.settings.get("pose_backend", config.POSE_BACKEND)
        if backend in ("auto", "mediapipe", "cv2"):
            config.POSE_BACKEND = backend
        self.camera = CameraManager(self.settings["camera_index"])
        self.pose_tracker = PoseTracker()
        self._pose_init_started = False
        self.calibrator = Calibrator(
            CalibrationData.from_dict(self.settings.get("calibration")))
        self.distance = DistanceEstimator(
            self.calibrator.existing or CalibrationData(),
            sensitivity=self.settings["distance_sensitivity"])
        self.gestures = GestureDetector(
            punch_sensitivity=self.settings["punch_sensitivity"])
        self.keyboard = KeyboardInput()

        # final logical input produced by the pipeline
        self.tracking = TrackingData.empty()
        self.last_tracking = self.tracking
        self.last_pose = None
        self.last_camera_frame = None
        self._smooth_x = 0.5
        self._resting_ratio: Optional[float] = None
        self._resting_lateral: Optional[float] = None
        self._stable_depth_delta = 0.0
        self._tracking_lost_time = 0.0
        self._pose_gone = True

        # ------------------------------------------------------------------
        # flags
        # ------------------------------------------------------------------
        self.debug_overlay = bool(self.settings.get("debug_mode"))
        self.dt = 0.016
        self._shake_offset = (0.0, 0.0)
        self._fullscreen = bool(self.settings.get("fullscreen"))
        self._apply_window_mode()

        # ------------------------------------------------------------------
        # scenes
        # ------------------------------------------------------------------
        from ui.main_menu import MainMenu
        self.states.push(MainMenu(self))

    # ------------------------------------------------------------------
    # audio wiring
    # ------------------------------------------------------------------
    def _wire_audio_events(self) -> None:
        self.events.subscribe("hit", lambda **kw: self.audio.play("hit"))
        self.events.subscribe("block", lambda **kw: self.audio.play("block"))
        self.events.subscribe("knockdown", lambda **kw: self.audio.play("knockdown"))
        self.events.subscribe("victory", lambda **kw: self.audio.play("victory"))
        self.events.subscribe("defeat", lambda **kw: self.audio.play("defeat"))

    # ------------------------------------------------------------------
    # window
    # ------------------------------------------------------------------
    def _apply_window_mode(self) -> None:
        flags = pygame.RESIZABLE | (pygame.FULLSCREEN if self._fullscreen else 0)
        self.screen = pygame.display.set_mode(
            (config.BASE_WIDTH, config.BASE_HEIGHT), flags)

    def toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        self.settings["fullscreen"] = self._fullscreen
        self._apply_window_mode()

    # ------------------------------------------------------------------
    # camera helpers
    # ------------------------------------------------------------------
    def camera_is_open(self) -> bool:
        return self.camera._cap is not None and self.camera.status == "CONNECTED"

    def camera_status_text(self) -> str:
        if self.settings["input_mode"] == "keyboard":
            return "KEYBOARD MODE"
        if not self.pose_tracker.available:
            return "POSE OFF"
        return self.camera.status

    def _ensure_camera(self) -> bool:
        """Open the camera and initialize pose tracking if needed."""
        if self.camera_is_open():
            return True
        if self.camera.open(self.settings["camera_index"]):
            if not self.pose_tracker.available and not self._pose_init_started:
                self._pose_init_started = True
                self.pose_tracker.initialize()
            return True
        return False

    # ------------------------------------------------------------------
    # the camera -> TrackingData pipeline
    # ------------------------------------------------------------------
    def poll_camera(self, dt: float) -> TrackingData:
        """Capture one frame, run pose + gestures, produce TrackingData."""
        ok, frame = self.camera.read()
        self.last_tracking = self.tracking
        if not ok:
            self._pose_gone = True
            self.tracking = TrackingData.empty()
            return self.tracking

        self.last_camera_frame = frame
        pose = self.pose_tracker.process(frame) if self.pose_tracker.available else None
        self.last_pose = pose

        if pose is not None and pose.present and pose.body_confidence >= config.POSE_MIN_BODY_CONFIDENCE:
            self._pose_gone = False
            self._tracking_lost_time = 0.0

            # gestures
            self.gestures.update(pose, dt, self.calibrator.existing)
            arms_active = self._arms_active(pose)

            # Raised arms distort shoulder width, so use torso-only distance
            # while punching/guarding.  Position itself is held below.
            ratio, level, scale = self.distance.update(
                pose, dt, torso_only=arms_active)
            self._update_tracking_data(pose, ratio, level, scale, dt,
                                       freeze_depth=arms_active)
        else:
            # tracking lost: freeze movement, clear gestures, never teleport
            self._pose_gone = True
            self._tracking_lost_time += dt
            empty_pose = PoseData(present=False)
            self.gestures.update(empty_pose, dt, self.calibrator.existing)
            self.tracking = TrackingData(
                present=False,
                horizontal_position=self._smooth_x,
                distance_ratio=1.0,
                distance_level="MEDIUM",
                player_scale=1.0,
                pose_present=False,
            )
        return self.tracking

    def _arms_active(self, pose) -> bool:
        """Whether arm motion can corrupt shoulder-based measurements."""
        if (self.gestures.guard or self.gestures.left_punch or
                self.gestures.right_punch):
            return True
        left_wrist = pose.lm(LM_LEFT_WRIST)
        right_wrist = pose.lm(LM_RIGHT_WRIST)
        left_shoulder = pose.lm(LM_LEFT_SHOULDER)
        right_shoulder = pose.lm(LM_RIGHT_SHOULDER)
        if not all((left_wrist, right_wrist, left_shoulder, right_shoulder)):
            return False
        if min(left_wrist[3], right_wrist[3], left_shoulder[3],
               right_shoulder[3]) < config.POSE_MIN_LANDMARK_VIS:
            return False
        shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
        return left_wrist[1] < shoulder_y or right_wrist[1] < shoulder_y

    def _update_tracking_data(self, pose, ratio: float, level: str,
                              scale: float, dt: Optional[float] = None,
                              freeze_depth: bool = False) -> None:
        # horizontal position = mirrored lateral (body center) + depth
        # (calibration-relative distance). The player faces the camera, so
        # stepping right means the body moves to image-left -> mirror it.
        # Closer to the camera (ratio > 1) advances right toward the enemy,
        # farther (ratio < 1) retreats left. The depth term needs calibration.
        lateral = self._lateral_position(pose)
        if self.settings.get("mirror_input"):
            lateral = 1.0 - lateral
        if self._resting_ratio is None:
            self._resting_ratio = ratio
        if self._resting_lateral is None:
            self._resting_lateral = lateral

        lateral_delta = self._apply_deadband(
            lateral - self._resting_lateral,
            config.TRACKING_LATERAL_DEADBAND)
        if freeze_depth:
            # Preserve the last trustworthy distance component.  Resetting
            # it to zero would itself make the boxer dash during a punch.
            depth_delta = self._stable_depth_delta
        else:
            depth_delta = self._apply_deadband(
                ratio - self._resting_ratio, config.TRACKING_DEPTH_DEADBAND)
            self._stable_depth_delta = depth_delta
        target = config.DEPTH_NEUTRAL_HP
        target += lateral_delta * self.settings["sensitivity"]
        target += depth_delta * config.DEPTH_MOVE_GAIN
        target = min(config.DEPTH_HP_MAX, max(config.DEPTH_HP_MIN, target))

        # This is time-based rather than a per-render-frame factor, so the
        # response stays consistent whether the camera runs at 10 or 30 pose
        # frames per second.
        frame_dt = self.dt if dt is None else dt
        smooth = max(0.0, min(1.0, self.settings["smoothing"]))
        response_time = config.TRACKING_RESPONSE_TIME + smooth * (
            config.TRACKING_RESPONSE_TIME_MAX - config.TRACKING_RESPONSE_TIME)
        alpha = 1.0 - pow(2.718281828459045, -max(0.0, frame_dt) / response_time)
        self._smooth_x += (target - self._smooth_x) * alpha

        tracking = TrackingData(
            present=True,
            horizontal_position=min(1.0, max(0.0, self._smooth_x)),
            distance_ratio=ratio,
            distance_level=level,
            left_punch=self.gestures.left_punch,
            right_punch=self.gestures.right_punch,
            left_haymaker=self.gestures.left_haymaker,
            right_haymaker=self.gestures.right_haymaker,
            is_charging=self.gestures.is_charging,
            is_charged=self.gestures.is_charged,
            charge_progress=self.gestures.charge_progress,
            guard=self.gestures.guard,
            hands_up=self.gestures.hands_up,
            player_scale=scale,
            body_confidence=pose.body_confidence,
            pose_present=True,
            frame_w=pose.frame_w,
            frame_h=pose.frame_h,
            debug={"left_punch": self.gestures.left_punch,
                   "right_punch": self.gestures.right_punch,
                   "guard": self.gestures.guard,
                   "charging": self.gestures.is_charging,
                   "charged": self.gestures.is_charged},
        )
        self.tracking = tracking

    @staticmethod
    def _apply_deadband(value: float, width: float) -> float:
        if abs(value) <= width:
            return 0.0
        return value - width if value > 0.0 else value + width

    @staticmethod
    def _lateral_position(pose) -> float:
        """Hips are the stable lateral anchor; arms never affect movement."""
        left_hip = pose.lm(LM_LEFT_HIP)
        right_hip = pose.lm(LM_RIGHT_HIP)
        if (left_hip is not None and right_hip is not None and
                left_hip[3] >= config.POSE_MIN_LANDMARK_VIS and
                right_hip[3] >= config.POSE_MIN_LANDMARK_VIS):
            return (left_hip[0] + right_hip[0]) / 2.0
        return pose.body_center_x

    def reset_tracking_position(self) -> None:
        """Start a fight at the fighter's neutral arena position.

        The first valid pose becomes the live resting reference.  This keeps
        fallback calibration (whose ratio is often far from 1.0) useful
        without moving a still player as a fight begins.
        """
        self._smooth_x = config.DEPTH_NEUTRAL_HP
        self._resting_ratio = None
        self._resting_lateral = None
        self._stable_depth_delta = 0.0

    def poll_camera_for_calibration(self):
        """Feed one camera frame through the pipeline; used by the
        calibration screen and the camera debug view."""
        if not self.camera_is_open():
            if not self.camera.open(self.settings["camera_index"]):
                return None, None
        dt = self.dt
        ok, frame = self.camera.read()
        if not ok:
            return None, None
        self.last_camera_frame = frame
        pose = self.pose_tracker.process(frame) if self.pose_tracker.available else None
        self.last_pose = pose
        if pose is not None and pose.present and pose.body_confidence >= config.POSE_MIN_BODY_CONFIDENCE:
            self.gestures.update(pose, dt, self.calibrator.existing)
            arms_active = self._arms_active(pose)
            ratio, level, scale = self.distance.update(
                pose, dt, torso_only=arms_active)
            self._update_tracking_data(pose, ratio, level, scale, dt,
                                       freeze_depth=arms_active)
        return self.tracking, pose

    def get_current_tracking(self) -> TrackingData:
        """The logical input for gameplay this frame (camera or keyboard)."""
        if self.settings["input_mode"] == "keyboard":
            data = self.keyboard.update(self.dt)
            self.last_tracking = data
            return data
        return self.poll_camera(self.dt)

    @property
    def tracking_lost_warning(self) -> bool:
        return (self.settings["input_mode"] == "camera" and
                self._pose_gone and
                self._tracking_lost_time > config.TRACKING_LOST_WARNING)

    # ------------------------------------------------------------------
    # settings application (called by the settings screen)
    # ------------------------------------------------------------------
    def apply_settings_changes(self) -> None:
        s = self.settings
        self.audio.set_volumes(s["music_volume"], s["sfx_volume"])
        self.gestures.set_punch_sensitivity(s["punch_sensitivity"])
        self.distance.set_sensitivity(s["distance_sensitivity"])
        calibration = CalibrationData.from_dict(s.get("calibration"))
        self.calibrator.existing = calibration
        if self.distance.set_calibration(calibration):
            # A real recalibration changes what "resting" means.  The next
            # valid pose establishes the new reference without a teleport.
            self._resting_ratio = None
            self._resting_lateral = None
            self._stable_depth_delta = 0.0
        if s["input_mode"] == "keyboard":
            self.camera.release()
        if s["fullscreen"] != self._fullscreen:
            self._fullscreen = bool(s["fullscreen"])
            self._apply_window_mode()
        if s.get("camera_index") != self.camera.index:
            self.camera.release()
            self.camera.index = int(s["camera_index"])
        self.save_manager.save_settings()

    # ------------------------------------------------------------------
    # game flow transitions
    # ------------------------------------------------------------------
    def start_new_game(self, slot_number: Optional[int] = None) -> None:
        slot = slot_number or int(self.settings.get("last_slot", 1))
        self.progression = Progression()
        self.level_manager = LevelManager(self.progression)
        if self.settings["input_mode"] == "camera":
            if not self._ensure_camera():
                from ui.screens import CameraErrorScreen
                self.states.push(CameraErrorScreen(self))
                return
            self.start_calibration()
        else:
            self._enter_fight()

    def load_save(self, slot: int) -> None:
        data = self.save_manager.load_slot(slot)
        if data is None:
            self.start_new_game(slot_number=slot)
            return
        self.settings["last_slot"] = slot
        if data.get("calibration"):
            self.settings["calibration"] = data["calibration"]
        self.progression = Progression()
        self.progression.from_dict(data)
        self.level_manager = LevelManager(self.progression)
        self.apply_settings_changes()
        if self.settings["input_mode"] == "camera":
            if not self._ensure_camera():
                from ui.screens import CameraErrorScreen
                self.states.push(CameraErrorScreen(self))
                return
            self.start_calibration()
        else:
            self._enter_fight()

    def show_load_game(self) -> None:
        from ui.screens import LoadGameScreen
        self.states.push(LoadGameScreen(self))

    def show_settings(self, back_to: str = "main_menu") -> None:
        from ui.settings import SettingsScene
        self.states.push(SettingsScene(self, back_to=back_to))

    def show_level_select(self) -> None:
        from ui.screens import LevelSelectScreen
        self.states.push(LevelSelectScreen(self))

    def show_camera_debug(self, back_to: str = "settings") -> None:
        from ui.screens import CameraDebugView
        self.states.push(CameraDebugView(self, back_to=back_to))

    def start_calibration(self, from_settings: bool = False) -> None:
        self._ensure_camera()
        from ui.screens import CalibrationScreen
        self.states.push(CalibrationScreen(self, from_settings=from_settings))

    def on_calibration_done(self, skip: bool = False, back: bool = False) -> None:
        # calibration data is already stored in settings when completed
        self.states.pop()
        if back:
            return
        if skip and not self.settings.get("calibration"):
            self.settings["calibration"] = CalibrationData().to_dict()
            self.apply_settings_changes()
        self._enter_fight()

    def _enter_fight(self) -> None:
        if self.settings["input_mode"] == "camera" and not self._ensure_camera():
            from ui.screens import CameraErrorScreen
            self.states.push(CameraErrorScreen(self))
            return
        from gameplay.fight_scene import FightScene
        self.states.push(FightScene(self))

    def fight_opponent(self, index: int) -> None:
        self.progression.start_fight(index)
        self.level_manager = LevelManager(self.progression)
        self._enter_fight()

    def next_fight(self) -> None:
        self.states.clear()
        self._enter_fight()

    def retry_fight(self) -> None:
        self.states.clear()
        self._enter_fight()

    def to_main_menu(self) -> None:
        self.states.clear()
        from ui.main_menu import MainMenu
        self.states.push(MainMenu(self))

    def save_current_progress(self) -> None:
        slot = int(self.settings.get("last_slot", 1))
        data = self.save_manager.new_slot_data(slot)
        data.update(self.progression.to_dict())
        data["calibration"] = self.settings.get("calibration")
        data["settings"] = dict(self.settings)
        self.save_manager.save_slot(slot, data)

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        try:
            while self.running:
                dt = min(0.05, self.clock.tick(config.FPS_TARGET) / 1000.0)
                self.dt = dt
                self.fps = self.clock.get_fps()

                for event in pygame.event.get():
                    event = self._logical_mouse_event(event)
                    if event.type == pygame.QUIT:
                        self.quit()
                    elif event.type == pygame.KEYDOWN:
                        key = pygame.key.name(event.key)
                        if key == "f3":
                            self.debug_overlay = not self.debug_overlay
                            self.settings["debug_mode"] = self.debug_overlay
                        elif key == "f11":
                            self.toggle_fullscreen()
                        self.keyboard.handle_event(event)
                    self.states.handle_event(event)

                self.states.update(dt)

                # ---- render (shake offset applied by blitting) ----------
                self.canvas.fill(config.COLORS["charcoal_dark"])
                scratch = pygame.Surface((config.BASE_WIDTH, config.BASE_HEIGHT))
                self.states.draw(scratch)
                shake_x, shake_y = self._current_shake()
                self.canvas.blit(scratch, (int(shake_x), int(shake_y)))
                if self.debug_overlay:
                    self._draw_debug_overlay()
                self._present()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _current_shake(self) -> tuple:
        # the fight scene owns the shake value; read it if present
        for scene in self.states._stack:
            if getattr(scene, "name", "") == "gameplay":
                shake = scene.combat.shake
                if shake > 0:
                    import random
                    return (random.uniform(-shake, shake),
                            random.uniform(-shake, shake))
        return (0.0, 0.0)

    def _present(self) -> None:
        """Scale the 1280x720 canvas onto the window with letterboxing."""
        w, h = self.screen.get_size()
        if (w, h) == (config.BASE_WIDTH, config.BASE_HEIGHT) and not self._fullscreen:
            self.screen.blit(self.canvas, (0, 0))
        else:
            scale = min(w / config.BASE_WIDTH, h / config.BASE_HEIGHT)
            sw, sh = int(config.BASE_WIDTH * scale), int(config.BASE_HEIGHT * scale)
            scaled = pygame.transform.scale(self.canvas, (sw, sh))
            self.screen.fill((0, 0, 0))
            self.screen.blit(scaled, ((w - sw) // 2, (h - sh) // 2))
        pygame.display.flip()

    def _logical_mouse_event(self, event: pygame.event.Event) -> pygame.event.Event:
        """Map physical window mouse positions onto the 1280x720 canvas."""
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                              pygame.MOUSEBUTTONUP):
            return event
        if not hasattr(event, "pos"):
            return event
        attrs = dict(event.dict)
        attrs["pos"] = self.window_to_canvas(event.pos)
        return pygame.event.Event(event.type, attrs)

    def window_to_canvas(self, position: tuple[int, int]) -> tuple[float, float]:
        """Inverse of _present's letterbox scaling, used by all UI hit tests."""
        width, height = self.screen.get_size()
        scale = min(width / config.BASE_WIDTH, height / config.BASE_HEIGHT)
        scaled_w = config.BASE_WIDTH * scale
        scaled_h = config.BASE_HEIGHT * scale
        offset_x = (width - scaled_w) / 2.0
        offset_y = (height - scaled_h) / 2.0
        return ((position[0] - offset_x) / scale,
                (position[1] - offset_y) / scale)

    # ------------------------------------------------------------------
    # debug overlay (F3)
    # ------------------------------------------------------------------
    def _draw_debug_overlay(self) -> None:
        f = self.fonts["tiny"]
        game_scene = None
        for scene in self.states._stack:
            if getattr(scene, "name", "") == "gameplay":
                game_scene = scene
                break

        pose = self.last_pose
        t = self.last_tracking        rows = [
            f"FPS: {self.fps:.0f}",
            f"CAMERA: {self.camera.status}",
            f"POSE: {'OK' if (pose and pose.present) else 'NONE'}",
            f"BODY CONFIDENCE: {t.body_confidence:.2f}" if t else "BODY CONFIDENCE: -",
            f"PLAYER X: {t.horizontal_position:.2f}" if t else "PLAYER X: -",
            f"DISTANCE: {t.distance_level}" if t else "DISTANCE: -",
            f"LEFT PUNCH: {bool(t.left_punch)}" if t else "LEFT PUNCH: -",
            f"RIGHT PUNCH: {bool(t.right_punch)}" if t else "RIGHT PUNCH: -",
            f"GUARD: {bool(t.guard)}" if t else "GUARD: -",
            f"CHARGING: {t.is_charging} ({t.charge_progress*100:.0f}%)" if t else "CHARGING: -",
            f"CHARGED: {t.is_charged}" if t else "CHARGED: -",
            f"PLAYER HP: {int(game_scene.player.hp)}" if game_scene else "PLAYER HP: -",
            f"ENEMY HP: {int(game_scene.enemy.hp)}" if game_scene else "ENEMY HP: -",
            f"STATE: {game_scene.enemy.state.upper()}" if game_scene else "STATE: -",
            f"INPUT: {self.settings['input_mode'].upper()}",
        ]
        panel = pygame.Surface((300, 20 * len(rows) + 16), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 170))
        self.canvas.blit(panel, (10, 10))
        y = 18
        for row in rows:
            surf = f.render(row, True, config.COLORS["debug"])
            self.canvas.blit(surf, (18, y))
            y += 20

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        try:
            self.save_manager.save_settings()
        except Exception:
            pass
        self.camera.release()
        self.pose_tracker.close()
        pygame.quit()
        log.info("Game shut down cleanly.")



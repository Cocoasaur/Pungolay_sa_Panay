"""Non-gameplay screens: victory, defeat, camera error, calibration,
level select, load game, and the camera debug view.
"""

from __future__ import annotations

import os
from typing import List, Optional

import pygame

import config
from core.state_manager import Scene
from ui.fonts import render_spaced, cached_text
from ui.assets import load_image

C = config.COLORS


def _load_screen_overlay(screen_id: str) -> Optional[pygame.Surface]:
    return load_image(
        os.path.join(config.SCREENS_DIR, f"{screen_id}.png"),
        (config.BASE_WIDTH, config.BASE_HEIGHT),
    )


def _draw_screen_overlay(surface: pygame.Surface, overlay: Optional[pygame.Surface]) -> None:
    if overlay is not None:
        surface.blit(overlay, (0, 0))


class _MenuMixin:
    """Shared keyboard/mouse navigation for simple option lists."""

    def _nav(self, event, count: int) -> bool:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("up", "w"):
                self.selected = (self.selected - 1) % count
                self.game.audio.play("menu_move")
                return True
            if key in ("down", "s"):
                self.selected = (self.selected + 1) % count
                self.game.audio.play("menu_move")
                return True
            if key in ("return", "space"):
                self._activate()
                return True
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self._activate()
                    return True
        return False

    def _draw_buttons(
        self, surface, labels: List[str], y0: int, center_x: int, disabled=()
    ) -> None:
        f = self.game.fonts
        self._rects = []
        y = y0
        for i, label in enumerate(labels):
            hover = i == self.selected and i not in disabled
            text = cached_text(
                f["medium"],
                label,
                C["text_faint"] if i in disabled else C["title_white"] if hover else C["text"],
            )
            rect = pygame.Rect(center_x - 130, y - 14, 260, 46)
            self._rects.append(rect)
            if hover:
                pygame.draw.rect(surface, (52, 46, 40, 200), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 46))
            surface.blit(text, text.get_rect(center=(center_x, y + 8)))
            y += 56


# ---------------------------------------------------------------------------
class VictoryScreen(Scene, _MenuMixin):
    name = "victory"

    def __init__(
        self, game, enemy_name: Optional[str] = None, is_final: Optional[bool] = None
    ) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self._screen_overlay = _load_screen_overlay(self.name)
        self.enemy_name = game.progression.opponent["name"] if enemy_name is None else enemy_name
        self.is_final = game.progression.is_final_fight if is_final is None else is_final

    def enter(self) -> None:
        self.selected = 0
        self.game.audio.play("victory")

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == 0:  # NEXT FIGHT / MAIN MENU handled below
            if self.is_final:
                self.game.to_main_menu()
            else:
                self.game.next_fight()
        else:
            self.game.to_main_menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, 1 if self.is_final else 2)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        _draw_screen_overlay(surface, self._screen_overlay)
        f = self.game.fonts
        title = f["big"].render("YOU WIN", True, C["title_white"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 210)))
        subtitle = f["medium"].render(
            f"YOU DEFEATED {self.enemy_name.upper()}", True, C["text_dim"]
        )
        surface.blit(subtitle, subtitle.get_rect(center=(config.BASE_WIDTH // 2, 290)))
        if self.is_final:
            champion = f["medium"].render("PANAY CHAMPION", True, C["accent_red_bright"])
            surface.blit(champion, champion.get_rect(center=(config.BASE_WIDTH // 2, 330)))
        labels = ["MAIN MENU"] if self.is_final else ["NEXT FIGHT", "MAIN MENU"]
        self._draw_buttons(surface, labels, 400, config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class DefeatScreen(Scene, _MenuMixin):
    name = "defeat"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self.enemy_name = ""
        self._screen_overlay = _load_screen_overlay(self.name)

    def enter(self) -> None:
        self.selected = 0
        self.enemy_name = self.game.progression.opponent["name"]
        self.game.audio.play("defeat")

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == 0:
            self.game.retry_fight()
        else:
            self.game.to_main_menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        self._nav(event, 2)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        _draw_screen_overlay(surface, self._screen_overlay)
        f = self.game.fonts
        title = f["big"].render("YOU LOST", True, C["hp_red"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 210)))
        subtitle = f["medium"].render(
            f"{self.enemy_name.upper()} WINS THE ROUND", True, C["text_dim"]
        )
        surface.blit(subtitle, subtitle.get_rect(center=(config.BASE_WIDTH // 2, 290)))
        self._draw_buttons(surface, ["RETRY", "MAIN MENU"], 400, config.BASE_WIDTH // 2)


# ---------------------------------------------------------------------------
class CameraErrorScreen(Scene, _MenuMixin):
    name = "camera_error"

    def __init__(self, game, message=""):
        super().__init__(game)
        self.message = message or "Camera unavailable. Retry or use keyboard controls."
        self.selected = 0
        self._rects = []
        self._screen_overlay = _load_screen_overlay(self.name)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.states.pop()
            return
        self._nav(event, 3)

    def _activate(self):
        if self.selected == 0:
            self.game.camera.release_async()
            self.game.states.pop()
            self.game.start_calibration()
        elif self.selected == 1:
            self.game.settings["input_mode"] = "keyboard"
            self.game.apply_settings_changes()
            self.game._enter_fight()
        else:
            self.game.to_main_menu()

    def draw(self, surface):
        surface.fill(C["charcoal_dark"])
        _draw_screen_overlay(surface, self._screen_overlay)
        f = self.game.fonts
        title = f["large"].render("CAMERA UNAVAILABLE", True, C["hp_red"])
        surface.blit(title, title.get_rect(center=(640, 190)))
        message = f["small"].render(self.message, True, C["text"])
        surface.blit(message, message.get_rect(center=(640, 270)))
        self._draw_buttons(surface, ["RETRY", "KEYBOARD MODE", "MAIN MENU"], 350, 640)


class CalibrationScreen(Scene, _MenuMixin):
    """Nonblocking camera setup, calibration, then an explicit practice/start step."""

    name = "calibration"

    def __init__(self, game, from_settings=False):
        super().__init__(game)
        self.from_settings = from_settings
        self.return_scene = game.states.current
        self.selected = 0
        self._rects = []
        self._phase = "connecting"
        self._result_text = ""
        self._preview = None
        self._practice = {"LEFT PUNCH": False, "RIGHT PUNCH": False, "BLOCK": False}
        self._screen_overlay = _load_screen_overlay(self.name)

    def enter(self):
        self.game._ensure_camera()

    def _actions(self):
        if self._phase == "practice":
            return [
                "RETURN TO SETTINGS" if self.from_settings else "START FIGHT",
                "RECALIBRATE",
                "CANCEL",
            ]
        actions = ["RETRY CAMERA"] if self._phase == "error" else []
        if self._phase != "error" and self.game.settings.get("calibration"):
            actions.append("USE SAVED CALIBRATION")
        return actions + ["KEYBOARD MODE", "CANCEL"]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._cancel()
            return
        self._nav(event, len(self._actions()))

    def _cancel(self):
        if not self.game.states.return_to(self.return_scene):
            self.game.to_main_menu()
        if getattr(self.game.states.current, "name", None) != "settings":
            self.game.camera.release_async()

    def _skip(self):
        self._cancel()

    def _activate(self):
        action = self._actions()[min(self.selected, len(self._actions()) - 1)]
        game = self.game
        if action == "CANCEL":
            self._cancel()
        elif action == "KEYBOARD MODE":
            game.settings["input_mode"] = "keyboard"
            game.apply_settings_changes()
            game.on_calibration_done()
        elif action == "USE SAVED CALIBRATION":
            if game._ensure_camera():
                self._phase = "practice"
                self.selected = 0
        elif action in ("RETRY CAMERA", "RECALIBRATE"):
            if action == "RETRY CAMERA":
                game.camera.release_async()
            self._phase = "connecting"
            self.selected = 0
            game._ensure_camera()
        elif action in ("START FIGHT", "RETURN TO SETTINGS"):
            if game.settings["input_mode"] == "keyboard" or game._ensure_camera():
                game.on_calibration_done()

    def update(self, dt):
        game = self.game
        tracking, pose = game.poll_camera_for_calibration()
        status = game.camera.status
        if status in ("CAMERA NOT DETECTED", "CAMERA LOST", "POSE UNAVAILABLE"):
            self._phase = "error"
            self.selected = min(self.selected, len(self._actions()) - 1)
        if game.last_camera_frame is not None and pose is not None:
            frame = game.pose_tracker.draw_debug_frame(
                game.last_camera_frame, pose, raw=game.raw_landmarks
            )
            frame = game.gestures.draw_punch_boundary(frame, pose, game.calibrator.existing)
            rgb = frame[:, :, ::-1].copy()
            image = pygame.image.frombuffer(rgb, (rgb.shape[1], rgb.shape[0]), "RGB")
            self._preview = pygame.transform.smoothscale(image, (640, 360))
        if self._phase == "connecting" and pose is not None and pose.present:
            game.calibrator.start()
            self._phase = "collecting"
        if self._phase == "collecting" and game._sample_is_new:
            if game.calibrator.process(pose, game._sample_dt):
                game.settings["calibration"] = game.calibrator.finish().to_dict()
                game.apply_settings_changes()
                self._phase = "practice"
                self.selected = 0
                self._result_text = "Calibration saved. Try each action."
                game.audio.play("menu_select")
        if self._phase == "practice" and tracking is not None:
            self._practice["LEFT PUNCH"] |= tracking.left_punch or tracking.left_haymaker
            self._practice["RIGHT PUNCH"] |= tracking.right_punch or tracking.right_haymaker
            self._practice["BLOCK"] |= tracking.guard

    def draw(self, surface):
        surface.fill(C["charcoal_dark"])
        f = self.game.fonts
        surface.blit(f["large"].render("CAMERA SETUP", True, C["title_white"]), (60, 40))
        surface.blit(
            f["small"].render("CONNECT  >  CALIBRATE  >  PRACTICE  >  START", True, C["text_dim"]),
            (60, 88),
        )
        pygame.draw.rect(surface, (28, 26, 24), (60, 125, 640, 360), border_radius=6)
        if self._preview is not None:
            surface.blit(self._preview, (60, 125))
        game = self.game
        surface.blit(f["small"].render(game.camera.status, True, C["warn_yellow"]), (750, 135))
        if self._phase == "collecting":
            steps = [
                "",
                "Stand naturally; upper body visible.",
                "Raise both arms.",
                "Hold both gloves near your face.",
                "Turn into your side boxing stance.",
                "Done",
            ]
            phase = min(game.calibrator.phase, len(steps) - 1)
            lines = [f"STEP {phase} / 4", steps[phase], "Hold the pose until the bar fills."]
            progress = min(1.0, game.calibrator.hold_time)
        elif self._phase == "practice":
            lines = ["READY TO PRACTICE", self._result_text] + [
                f"{'OK' if done else 'TRY'}: {name}" for name, done in self._practice.items()
            ]
            progress = 1
        elif self._phase == "error":
            lines = ["CAMERA NEEDS ATTENTION", "Retry or choose Keyboard Mode."]
            progress = 0
        else:
            lines = ["CONNECTING / LOADING TRACKING", "You can cancel while it starts."]
            progress = 0
        for i, line in enumerate(lines):
            surface.blit(f["small"].render(line, True, C["text"]), (750, 190 + i * 32))
        pygame.draw.rect(surface, C["border"], (750, 420, 420, 14))
        pygame.draw.rect(surface, C["warm_glow"], (750, 420, int(420 * progress), 14))
        surface.blit(f["small"].render("LEFT: CYAN    RIGHT: ORANGE", True, C["text"]), (750, 460))
        actions = self._actions()
        disabled = []
        for i, action in enumerate(actions):
            if action in ("USE SAVED CALIBRATION", "START FIGHT") and not (
                game.camera_is_open() and game.pose_tracker.available
            ):
                disabled.append(i)
        self._draw_buttons(surface, actions, 520, 640, disabled=disabled)

    def exit(self):
        self.game.save_manager.flush_settings(force=True)


class LoadGameScreen(Scene, _MenuMixin):
    name = "load_game"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self._slots: List[dict] = []
        self._screen_overlay = _load_screen_overlay(self.name)

    def enter(self) -> None:
        self.selected = 0
        self._slots = []
        for slot in range(1, config.NUM_SAVE_SLOTS + 1):
            summary = self.game.save_manager.slot_summary(slot)
            self._slots.append(summary or {"slot": slot, "exists": False})

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.states.pop()
            return
        if self._nav(event, len(self._slots) + 1):
            return

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        if self.selected == len(self._slots):
            self.game.states.pop()  # BACK
            return
        slot = self._slots[self.selected]
        if slot["exists"]:
            self.game.load_save(slot["slot"])
        else:
            self.game.start_new_game(slot_number=slot["slot"])

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        _draw_screen_overlay(surface, self._screen_overlay)
        f = self.game.fonts
        title = f["large"].render("LOAD GAME", True, C["title_white"])
        surface.blit(title, (60, 50))
        hint = f["tiny"].render("EMPTY SLOTS START A NEW GAME", True, C["text_faint"])
        surface.blit(hint, (60, 92))

        self._rects = []
        y = 150
        for i, slot in enumerate(self._slots):
            rect = pygame.Rect(60, y, 700, 64)
            self._rects.append(rect)
            hover = i == self.selected
            if hover:
                pygame.draw.rect(surface, (52, 46, 40), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 64))
            pygame.draw.rect(surface, C["border"], rect, 1)
            head = f["medium"].render(
                f"SLOT {slot['slot']}", True, C["title_white"] if hover else C["text"]
            )
            surface.blit(head, (rect.x + 18, rect.y + 8))
            if slot["exists"]:
                sub = f["small"].render(
                    f"{slot['timestamp']}   -   {slot['opponent']} @ {slot['location']}"
                    f"   -   {len(slot['defeated'])} WINS",
                    True,
                    C["text_dim"],
                )
            else:
                sub = f["small"].render("EMPTY", True, C["text_faint"])
            surface.blit(sub, (rect.x + 18, rect.y + 36))
            y += 76

        back_rect = pygame.Rect(60, y + 6, 700, 44)
        self._rects.append(back_rect)
        hover = self.selected == len(self._slots)
        if hover:
            pygame.draw.rect(surface, (52, 46, 40), back_rect)
            pygame.draw.rect(surface, C["accent_red"], (back_rect.x, back_rect.y, 4, 44))
        back = f["medium"].render("BACK", True, C["title_white"] if hover else C["text"])
        surface.blit(back, (back_rect.x + 18, back_rect.y + 10))


# ---------------------------------------------------------------------------
class LevelSelectScreen(Scene, _MenuMixin):
    name = "level_select"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.selected = 0
        self._rects = []
        self._screen_overlay = _load_screen_overlay(self.name)

    def enter(self) -> None:
        self.selected = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.states.pop()
            return
        self._nav(event, len(self.game.progression.unlocked_opponents()) + 1)

    def _activate(self) -> None:
        self.game.audio.play("menu_select")
        unlocked = self.game.progression.unlocked_opponents()
        if self.selected == len(unlocked):
            self.game.states.pop()
            return
        self.game.fight_opponent(unlocked[self.selected])

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C["charcoal_dark"])
        _draw_screen_overlay(surface, self._screen_overlay)
        f = self.game.fonts
        title = f["large"].render("LEVEL SELECT", True, C["title_white"])
        surface.blit(title, (60, 50))

        self._rects = []
        y = 140
        unlocked = self.game.progression.unlocked_opponents()
        for i, index in enumerate(unlocked):
            enemy = config.ENEMIES[config.OPPONENT_ORDER[index]]
            location = config.LOCATIONS[config.LOCATION_ORDER[index]]
            rect = pygame.Rect(60, y, 700, 58)
            self._rects.append(rect)
            hover = i == self.selected
            if hover:
                pygame.draw.rect(surface, (52, 46, 40), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 58))
            pygame.draw.rect(surface, C["border"], rect, 1)
            name = f["medium"].render(
                f"{enemy['name'].upper()}", True, C["title_white"] if hover else C["text"]
            )
            surface.blit(name, (rect.x + 18, rect.y + 8))
            sub = f["small"].render(
                f"{enemy.get('title','').upper()}  -  {location['name'].upper()}",
                True,
                C["text_dim"],
            )
            surface.blit(sub, (rect.x + 18, rect.y + 34))
            y += 68

        back_rect = pygame.Rect(60, y + 6, 700, 44)
        self._rects.append(back_rect)
        if self.selected == len(unlocked):
            pygame.draw.rect(surface, (52, 46, 40), back_rect)
            pygame.draw.rect(surface, C["accent_red"], (back_rect.x, back_rect.y, 4, 44))
        back = f["medium"].render(
            "BACK", True, C["title_white"] if self.selected == len(unlocked) else C["text"]
        )
        surface.blit(back, (back_rect.x + 18, back_rect.y + 10))


# ---------------------------------------------------------------------------
class CameraDebugView(Scene):
    name = "camera_debug"

    def __init__(self, game, back_to="settings", return_scene=None):
        super().__init__(game)
        self.back_to = back_to
        self.return_scene = return_scene or game.states.current
        self.fonts = game.fonts
        self._preview = None
        self.back_rect = pygame.Rect(880, 640, 300, 44)
        self.retry_rect = pygame.Rect(880, 530, 300, 42)
        self.keyboard_rect = pygame.Rect(880, 582, 300, 42)
        self._screen_overlay = _load_screen_overlay(self.name)

    def enter(self):
        self.game._ensure_camera()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.game.raw_landmarks = not self.game.raw_landmarks
            elif event.key == pygame.K_ESCAPE:
                self._back()
            elif event.key == pygame.K_t:
                self._retry()
            elif event.key == pygame.K_k:
                self._keyboard()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                self._back()
            elif self.retry_rect.collidepoint(event.pos):
                self._retry()
            elif self.keyboard_rect.collidepoint(event.pos):
                self._keyboard()

    def _back(self):
        if not self.game.states.return_to(self.return_scene):
            self.game.to_main_menu()

    def _retry(self):
        self.game.camera.release_async()
        self.game._ensure_camera()

    def _keyboard(self):
        self.game.settings["input_mode"] = "keyboard"
        self.game.apply_settings_changes()
        self._back()
        current = self.game.states.current
        if getattr(current, "name", None) == "settings":
            current._switch_tab(0)

    def update(self, dt):
        game = self.game
        tracking, pose = game.poll_camera_for_calibration()
        if game.last_camera_frame is not None and pose is not None:
            frame = game.pose_tracker.draw_debug_frame(
                game.last_camera_frame, pose, raw=game.raw_landmarks
            )
            frame = game.gestures.draw_punch_boundary(frame, pose, game.calibrator.existing)
            rgb = frame[:, :, ::-1].copy()
            image = pygame.image.frombuffer(rgb, (rgb.shape[1], rgb.shape[0]), "RGB")
            self._preview = pygame.transform.smoothscale(image, (800, 450))

    def draw(self, surface):
        import time

        game = self.game
        f = self.fonts
        camera = game.camera
        pose = game.last_pose
        surface.fill(C["charcoal_dark"])
        surface.blit(f["large"].render("CAMERA DEBUG", True, C["title_white"]), (40, 20))
        if self._preview is not None:
            surface.blit(self._preview, (40, 80))
        else:
            pygame.draw.rect(surface, (28, 26, 24), (40, 80, 800, 450))
        rows = [
            ("Camera", camera.status),
            ("Backend", game.pose_tracker.backend),
            ("Camera FPS", f"{camera.fps_camera:.0f}"),
            ("Pose FPS", f"{camera.fps_pose:.0f}"),
            ("Inference", f"{camera.time_inference:.1f} ms"),
            (
                "Sample age",
                f"{max(0,time.monotonic()-(game._last_sample_time or time.monotonic()))*1000:.0f} ms",
            ),
            ("Dropped", str(camera.dropped_frames)),
            ("Landmarks", "RAW" if game.raw_landmarks else "FILTERED"),
        ]
        for side, idx in (("Left", 15), ("Right", 16)):
            point = pose.lm(idx) if pose else None
            hand = game.gestures.left_hand if side == "Left" else game.gestures.right_hand
            rows.extend(
                [
                    (side + " wrist", f"{point[3]:.2f}" if point else "LOST"),
                    (side + " arm", "ARMED" if hand.line_armed else "RETRACT"),
                ]
            )
        for i, (label, value) in enumerate(rows):
            surface.blit(f["small"].render(label + ":", True, C["text_dim"]), (880, 90 + i * 30))
            surface.blit(f["small"].render(value, True, C["text"]), (1010, 90 + i * 30))
        for i, text in enumerate(
            (
                "LEFT: CYAN    RIGHT: ORANGE",
                "R: toggle raw / filtered landmarks",
                "Yellow line: extend past it, then retract.",
            )
        ):
            surface.blit(f["small"].render(text, True, C["text"]), (40, 560 + i * 28))
        for rect, label in (
            (self.retry_rect, "RETRY / T"),
            (self.keyboard_rect, "KEYBOARD MODE / K"),
        ):
            pygame.draw.rect(surface, C["border"], rect, border_radius=5)
            text = f["small"].render(label, True, C["title_white"])
            surface.blit(text, text.get_rect(center=rect.center))
        pygame.draw.rect(surface, C["border"], self.back_rect, border_radius=5)
        text = f["medium"].render("BACK / ESC", True, C["title_white"])
        surface.blit(text, text.get_rect(center=self.back_rect.center))

    def exit(self):
        self.game.save_manager.flush_settings(force=True)
        if getattr(self.game.states.current, "name", None) == "main_menu":
            self.game.camera.release_async()

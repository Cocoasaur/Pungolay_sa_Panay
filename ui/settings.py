"""Three responsive settings pages with mouse and keyboard controls."""

from __future__ import annotations
import time
import pygame
import config
from core.state_manager import Scene
from ui.assets import load_image
from ui.fonts import cached_text
from camera.camera_manager import probe_cameras  # compatibility; never called by the UI

C = config.COLORS


class SettingsScene(Scene):
    name = "settings"
    TABS = ("CONTROLS", "CAMERA & TRACKING", "AUDIO & DISPLAY")

    def __init__(self, game, back_to="main_menu"):
        super().__init__(game)
        self.back_to = back_to
        self.fonts = game.fonts
        self.tab = 0
        self.selected = 0
        self._rects = []
        self._rows = []
        self._drag_row = None
        self._mouse_pos = (-1, -1)
        self.overlay = load_image(config.SCREENS_DIR + "/settings.png", (1280, 720))
        self.cameras = list(game.camera.devices)
        self.back_rect = pygame.Rect(60, 650, 180, 44)
        self.retry_rect = pygame.Rect(760, 600, 180, 42)
        self.keyboard_rect = pygame.Rect(960, 600, 260, 42)
        self.tab_rects = [pygame.Rect(60 + i * 390, 115, 375, 42) for i in range(3)]
        self._build_rows()

    def _build_rows(self):
        def row(key, label, kind, **kw):
            return dict(key=key, label=label, type=kind, **kw)

        if self.tab == 0:
            self._rows = [
                row("input_mode", "INPUT MODE", "list", options=["camera", "keyboard"]),
                row("sensitivity", "MOVEMENT SENSITIVITY", "range", min=0.5, max=2.0, step=0.1),
                row("smoothing", "MOVEMENT SMOOTHING", "range", min=0, max=1, step=0.05),
                row("punch_sensitivity", "PUNCH SENSITIVITY", "range", min=0.5, max=3.0, step=0.1),
                row(
                    "distance_sensitivity",
                    "DISTANCE SENSITIVITY",
                    "range",
                    min=0.5,
                    max=2.0,
                    step=0.1,
                ),
            ]
        elif self.tab == 1:
            self._rows = [
                row("camera_index", "CAMERA DEVICE", "list", options=self.cameras or [0]),
                row(
                    "punch_line_reach", "PUNCH LINE DISTANCE", "range", min=0.55, max=0.9, step=0.05
                ),
                row("mirror_input", "MIRROR MOVEMENT", "bool"),
                row("raw_landmarks", "RAW ARM LANDMARKS", "diagnostic"),
                row("scan", "RESCAN CAMERAS", "action"),
                row("camera_debug", "OPEN CAMERA DEBUG", "action"),
                row("recalibrate", "RECALIBRATE CAMERA", "action"),
            ]
        else:
            self._rows = [
                row("music_volume", "MUSIC VOLUME", "range", min=0, max=1, step=0.05),
                row("sfx_volume", "SFX VOLUME", "range", min=0, max=1, step=0.05),
                row("fullscreen", "FULLSCREEN", "bool"),
                row("debug_mode", "DEBUG OVERLAY", "bool"),
            ]
        self._rects = [pygame.Rect(60, 185 + i * 58, 650, 48) for i in range(len(self._rows))]
        self.selected = min(self.selected, len(self._rows))

    def _value(self, row):
        return (
            self.game.raw_landmarks
            if row["type"] == "diagnostic"
            else self.game.settings.get(row["key"])
        )

    def _set(self, row, value):
        if row["type"] == "diagnostic":
            self.game.raw_landmarks = bool(value)
        else:
            self.game.settings[row["key"]] = value
            self.game.apply_settings_changes()
        self.game.audio.play("menu_move")

    def _switch_tab(self, index):
        self._drag_row = None
        self.tab = index % 3
        self.selected = 0
        self._build_rows()
        if self.tab == 1:
            self.game._ensure_camera()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key == "escape":
                self._leave()
            elif key == "tab":
                self._switch_tab(
                    self.tab + (-1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1)
                )
            elif key in ("up", "w"):
                self.selected = (self.selected - 1) % (len(self._rows) + 1)
            elif key in ("down", "s"):
                self.selected = (self.selected + 1) % (len(self._rows) + 1)
            elif key in ("left", "a", "right", "d", "return", "space"):
                self._change_value(key)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_row = None
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_pos = event.pos
            if self._drag_row is not None:
                self._set_slider(self._drag_row, event.pos[0])
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
            if self.back_rect.collidepoint(event.pos):
                self.selected = len(self._rows)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                self._leave()
                return
            if self.tab == 1 and self.retry_rect.collidepoint(event.pos):
                self.game.camera.release_async()
                self.game._ensure_camera()
                return
            if self.tab == 1 and self.keyboard_rect.collidepoint(event.pos):
                self.game.settings["input_mode"] = "keyboard"
                self.game.apply_settings_changes()
                self._switch_tab(0)
                return
            for i, rect in enumerate(self.tab_rects):
                if rect.collidepoint(event.pos):
                    self._switch_tab(i)
                    return
            for i, rect in enumerate(self._rects):
                if not rect.collidepoint(event.pos):
                    continue
                self.selected = i
                row = self._rows[i]
                if row["type"] == "range":
                    if event.pos[0] >= rect.x + 285:
                        self._drag_row = i
                        self._set_slider(i, event.pos[0])
                else:
                    self._change_value("right")
                return

    def _set_slider(self, index, x):
        row = self._rows[index]
        rect = self._rects[index]
        slider = pygame.Rect(rect.x + 285, rect.y + 15, rect.w - 350, 18)
        ratio = max(0, min(1, (x - slider.x) / slider.w))
        value = row["min"] + round(ratio * (row["max"] - row["min"]) / row["step"]) * row["step"]
        value = round(max(row["min"], min(row["max"], value)), 3)
        if value != self._value(row):
            self._set(row, value)

    def _change_value(self, key):
        if self.selected >= len(self._rows):
            if key in ("return", "space"):
                self._leave()
            return
        row = self._rows[self.selected]
        kind = row["type"]
        if kind == "action":
            self._activate_action()
            return
        value = self._value(row)
        step = -1 if key in ("left", "a") else 1
        if kind in ("bool", "diagnostic"):
            self._set(row, not value)
        elif kind == "list":
            options = row["options"]
            index = options.index(value) if value in options else 0
            self._set(row, options[(index + step) % len(options)])
        elif kind == "range" and key not in ("return", "space"):
            self._set(row, round(max(row["min"], min(row["max"], value + step * row["step"])), 3))

    def _activate_action(self):
        key = self._rows[self.selected]["key"]
        self.game.audio.play("menu_select")
        if key == "scan":
            self.game.camera.scan_async()
        elif key == "camera_debug":
            self.game.show_camera_debug(back_to=self.name)
        elif key == "recalibrate":
            self.game.start_calibration(from_settings=True)

    def _leave(self):
        self.game.save_manager.flush_settings(force=True)
        self.game.states.pop()
        if getattr(self.game.states.current, "name", None) == "main_menu":
            self.game.camera.release_async()

    def exit(self):
        self.game.save_manager.flush_settings(force=True)
        # A diagnostic visit must never leak a cached punch into the fight.
        self.game.gestures.left_punch = self.game.gestures.right_punch = False
        self.game.gestures.charge_completed = False

    def update(self, dt):
        if self.game.camera.devices != self.cameras:
            self.cameras = list(self.game.camera.devices)
            self._build_rows()
        if self.tab == 1:
            self.game.poll_camera_for_calibration()

    def draw(self, surface):
        f = self.fonts
        surface.fill(C["charcoal_dark"])
        if self.overlay is not None:
            surface.blit(self.overlay, (0, 0))
        surface.blit(f["large"].render("SETTINGS", True, C["title_white"]), (60, 40))
        surface.blit(
            f["small"].render(
                "TAB: PAGE   ARROWS: SELECT / CHANGE   ESC: BACK", True, C["text_dim"]
            ),
            (60, 88),
        )
        for i, rect in enumerate(self.tab_rects):
            pygame.draw.rect(
                surface, C["accent_red"] if i == self.tab else C["border"], rect, border_radius=6
            )
            if rect.collidepoint(self._mouse_pos):
                pygame.draw.rect(surface, C["warm_glow"], rect, 1, border_radius=6)
            text = cached_text(f["medium"], self.TABS[i], C["title_white"])
            surface.blit(text, text.get_rect(center=rect.center))
        for i, (row, rect) in enumerate(zip(self._rows, self._rects)):
            pygame.draw.rect(
                surface, (52, 46, 40) if i == self.selected else (28, 26, 24), rect, border_radius=4
            )
            if i == self.selected:
                pygame.draw.rect(surface, C["warm_glow"], rect, 1, border_radius=4)
            surface.blit(
                cached_text(f["small"], row["label"], C["text"]), (rect.x + 14, rect.y + 16)
            )
            kind = row["type"]
            if kind == "action":
                value = "SCANNING..." if row["key"] == "scan" and self.game.camera.scanning else ">"
            else:
                val = self._value(row)
                if kind in ("bool", "diagnostic"):
                    value = "ON" if val else "OFF"
                elif kind == "range":
                    value = f"{round(val*100)}%" if row["max"] <= 1 else f"{val:.1f}x"
                    slider = pygame.Rect(rect.x + 285, rect.y + 22, rect.w - 350, 5)
                    pygame.draw.rect(surface, C["border"], slider)
                    x = slider.x + int((val - row["min"]) / (row["max"] - row["min"]) * slider.w)
                    pygame.draw.circle(surface, C["warm_glow"], (x, slider.centery), 6)
                else:
                    value = f"< {str(val).upper()} >"
            text = f["small"].render(value, True, C["warn_yellow"])
            surface.blit(text, text.get_rect(midright=(rect.right - 12, rect.centery)))
        pygame.draw.rect(
            surface,
            C["accent_red"] if self.selected == len(self._rows) else C["border"],
            self.back_rect,
            border_radius=5,
        )
        text = f["medium"].render("BACK", True, C["title_white"])
        surface.blit(text, text.get_rect(center=self.back_rect.center))
        if self.tab == 1:
            game = self.game
            pose = game.last_pose
            frame = game.last_camera_frame
            if frame is not None and pose is not None:
                frame = game.pose_tracker.draw_debug_frame(frame, pose, raw=game.raw_landmarks)
                frame = game.gestures.draw_punch_boundary(frame, pose, game.calibrator.existing)
                rgb = frame[:, :, ::-1].copy()
                image = pygame.image.frombuffer(rgb, (rgb.shape[1], rgb.shape[0]), "RGB")
                surface.blit(pygame.transform.smoothscale(image, (460, 259)), (760, 190))
            else:
                pygame.draw.rect(surface, (30, 28, 26), (760, 190, 460, 259))
            for rect, label in (
                (self.retry_rect, "RETRY CAMERA"),
                (self.keyboard_rect, "USE KEYBOARD MODE"),
            ):
                pygame.draw.rect(surface, C["border"], rect, border_radius=4)
                if rect.collidepoint(self._mouse_pos):
                    pygame.draw.rect(surface, C["warm_glow"], rect, 1, border_radius=4)
                text = f["small"].render(label, True, C["text"])
                surface.blit(text, text.get_rect(center=rect.center))
            labels = [
                game.camera.status,
                "LEFT: CYAN    RIGHT: ORANGE",
                "The yellow line follows your torso.",
                "Sensitivity changes confidence, not distance.",
            ]
            for i, label in enumerate(labels):
                surface.blit(f["small"].render(label, True, C["text"]), (760, 470 + i * 27))
        elif self.tab == 0:
            for i, label in enumerate(
                (
                    "MOVE: A/D or arrow keys",
                    "PUNCH: tap J / K",
                    "CHARGE: hold J or K for 5 seconds",
                    "READY: your next punch uses the ability",
                    "BLOCK / GET UP: SPACE",
                    "Camera: use your anatomical left/right arm",
                )
            ):
                surface.blit(f["small"].render(label, True, C["text"]), (760, 210 + i * 36))

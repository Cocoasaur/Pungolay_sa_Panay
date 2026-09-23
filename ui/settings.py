"""Settings screen: a live-editable list of options.

Arrow keys / mouse move the selection, left-right (or Enter for actions)
changes values. Every change is applied immediately and persisted to
settings.json when leaving the screen.
"""

from __future__ import annotations

from typing import Callable, List

import pygame

import config
from camera.camera_manager import probe_cameras
from core.state_manager import Scene

C = config.COLORS


class SettingsScene(Scene):
    name = "settings"

    def __init__(self, game, back_to: str = "main_menu") -> None:
        super().__init__(game)
        self.back_to = back_to
        self.fonts = game.fonts
        self.selected = 0
        self.cameras = probe_cameras()
        if game.settings.get("camera_index") not in self.cameras and self.cameras:
            game.settings["camera_index"] = self.cameras[0]
        self._rows: List[dict] = []
        self._build_rows()
        self._rects: List[pygame.Rect] = []

    # ------------------------------------------------------------------
    def _build_rows(self) -> None:
        s = self.game.settings
        self._rows = [
            {"key": "music_volume", "label": "MUSIC VOLUME",
             "type": "range", "min": 0, "max": 100, "step": 5,
             "fmt": lambda v: f"{int(v)}%", "get": lambda: s["music_volume"] * 100,
             "set": lambda v: s.__setitem__("music_volume", v / 100)},
            {"key": "sfx_volume", "label": "SFX VOLUME",
             "type": "range", "min": 0, "max": 100, "step": 5,
             "fmt": lambda v: f"{int(v)}%", "get": lambda: s["sfx_volume"] * 100,
             "set": lambda v: s.__setitem__("sfx_volume", v / 100)},
            {"key": "camera_index", "label": "CAMERA INDEX",
             "type": "list",
             "get": lambda: s.get("camera_index", 0),
             "set": lambda v: s.__setitem__("camera_index", int(v)),
             "options": self.cameras or [0], "fmt": lambda v: f"CAM {v}"},
            {"key": "input_mode", "label": "INPUT MODE",
             "type": "list", "options": ["camera", "keyboard"],
             "fmt": lambda v: v.upper(),
             "get": lambda: s["input_mode"], "set": lambda v: s.__setitem__("input_mode", v)},
            {"key": "sensitivity", "label": "SENSITIVITY",
             "type": "range", "min": 50, "max": 200, "step": 10,
             "fmt": lambda v: f"{v / 100:.1f}x",
             "get": lambda: s["sensitivity"] * 100,
             "set": lambda v: s.__setitem__("sensitivity", v / 100)},
            {"key": "smoothing", "label": "MOVEMENT SMOOTHING",
             "type": "range", "min": 0, "max": 100, "step": 5,
             "fmt": lambda v: f"{int(v)}%",
             "get": lambda: s["smoothing"] * 100,
             "set": lambda v: s.__setitem__("smoothing", v / 100)},
            {"key": "punch_sensitivity", "label": "PUNCH SENSITIVITY",
             "type": "range", "min": 50, "max": 300, "step": 10,
             "fmt": lambda v: f"{v / 100:.1f}x",
             "get": lambda: s["punch_sensitivity"] * 100,
             "set": lambda v: s.__setitem__("punch_sensitivity", v / 100)},
            {"key": "distance_sensitivity", "label": "DISTANCE SENSITIVITY",
             "type": "range", "min": 50, "max": 200, "step": 10,
             "fmt": lambda v: f"{v / 100:.1f}x",
             "get": lambda: s["distance_sensitivity"] * 100,
             "set": lambda v: s.__setitem__("distance_sensitivity", v / 100)},
            {"key": "mirror_input", "label": "MIRROR INPUT",
             "type": "bool",
             "get": lambda: s["mirror_input"],
             "set": lambda v: s.__setitem__("mirror_input", bool(v)),
             "fmt": lambda v: "ON" if v else "OFF"},
            {"key": "fullscreen", "label": "FULLSCREEN",
             "type": "bool",
             "get": lambda: s["fullscreen"],
             "set": lambda v: s.__setitem__("fullscreen", bool(v)),
             "fmt": lambda v: "ON" if v else "OFF"},
            {"key": "debug_mode", "label": "DEBUG OVERLAY",
             "type": "bool",
             "get": lambda: s["debug_mode"],
             "set": lambda v: s.__setitem__("debug_mode", bool(v)),
             "fmt": lambda v: "ON" if v else "OFF"},
            {"key": "camera_debug", "label": "CAMERA DEBUG VIEW",
             "type": "action"},
            {"key": "recalibrate", "label": "RECALIBRATE CAMERA",
             "type": "action"},
            {"key": "back", "label": "BACK", "type": "action"},
        ]

    # ------------------------------------------------------------------
    def _row_value(self, row: dict):
        return row["get"]() if "get" in row else ""

    def _set_row(self, row: dict, value) -> None:
        if "set" in row:
            row["set"](value)

    def _apply_live(self) -> None:
        game = self.game
        game.apply_settings_changes()

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("up", "w"):
                self.selected = (self.selected - 1) % len(self._rows)
                self.game.audio.play("menu_move")
            elif key in ("down", "s"):
                self.selected = (self.selected + 1) % len(self._rows)
                self.game.audio.play("menu_move")
            elif key in ("right", "d", "left", "a", "return", "space"):
                self._change_value(key)
            elif key == "escape":
                self._leave()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self._activate_action()

    def _change_value(self, key: str) -> None:
        row = self._rows[self.selected]
        row_type = row["type"]

        if row_type == "action":
            self._activate_action()
            return

        if key in ("return", "space") and row_type == "bool":
            self._set_row(row, not row["get"]())
            self.game.audio.play("menu_select")
            self._apply_live()
            return

        if key in ("left", "a"):
            step = -1
        elif key in ("right", "d"):
            step = 1
        else:
            return

        if row_type == "range":
            value = row["get"]()
            value = max(row["min"], min(row["max"], value + step * row["step"]))
            self._set_row(row, value)
        elif row_type == "list":
            options = row["options"]
            value = row["get"]()
            index = options.index(value) if value in options else 0
            index = (index + step) % len(options)
            self._set_row(row, options[index])
        elif row_type == "bool":
            self._set_row(row, not row["get"]())
        self.game.audio.play("menu_move")
        self._apply_live()

    def _activate_action(self) -> None:
        row = self._rows[self.selected]
        self.game.audio.play("menu_select")
        if row["key"] == "back":
            self._leave()
        elif row["key"] == "camera_debug":
            self.game.show_camera_debug(back_to=self.name)
        elif row["key"] == "recalibrate":
            self.game.start_calibration(from_settings=True)

    def _leave(self) -> None:
        self.game.save_manager.save_settings()
        self.game.audio.set_volumes(self.game.settings["music_volume"],
                                    self.game.settings["sfx_volume"])
        if self.back_to == "pause":
            self.game.states.pop()
        else:
            self.game.states.pop()

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        f = self.fonts
        surface.fill(C["charcoal_dark"])

        title = f["large"].render("SETTINGS", True, C["title_white"])
        surface.blit(title, (60, 46))

        hint = f["tiny"].render("ARROWS SELECT  -  LEFT/RIGHT CHANGE  -  ESC BACK",
                                True, C["text_faint"])
        surface.blit(hint, (60, 90))

        self._rects = []
        x, y = 60, 140
        for i, row in enumerate(self._rows):
            selected = i == self.selected
            rect = pygame.Rect(x, y, 700, 38)
            self._rects.append(rect)
            if selected:
                pygame.draw.rect(surface, (52, 46, 40), rect)
                pygame.draw.rect(surface, C["accent_red"], (x, y, 4, 38))
            label = f["small"].render(row["label"], True,
                                      C["title_white"] if selected else C["text"])
            surface.blit(label, (x + 16, y + 9))
            if row["type"] != "action":
                value = self._row_value(row)
                value_surf = f["small"].render(row["fmt"](value), True,
                                               C["warn_yellow"] if selected else C["text_dim"])
                surface.blit(value_surf, value_surf.get_rect(midright=(x + 680, y + 19)))
            y += 44
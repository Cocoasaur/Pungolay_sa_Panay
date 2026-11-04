"""JSON-based persistence: game settings and three save slots.

Writes are atomic (temp file + rename) so a crash mid-write cannot corrupt a
slot. Missing or corrupted files never crash the game -- they are replaced
with defaults and reported.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import config

log = logging.getLogger(__name__)


class SaveManager:
    def __init__(self) -> None:
        os.makedirs(config.SAVES_DIR, exist_ok=True)
        self.settings: Dict[str, Any] = dict(config.DEFAULT_SETTINGS)
        self._load_settings()
        self._settings_due = None

    # ------------------------------------------------------------------
    # settings.json
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        data = self._read_json(config.SETTINGS_PATH)
        if data:
            for key, value in config.DEFAULT_SETTINGS.items():
                if key in data:
                    self.settings[key] = data[key]

    def save_settings(self) -> None:
        self._settings_due = None
        self._write_json(config.SETTINGS_PATH, self.settings)

    def schedule_settings(self):
        self._settings_due = time.monotonic() + 0.25

    def flush_settings(self, force=False):
        if self._settings_due is not None and (force or time.monotonic() >= self._settings_due):
            self.save_settings()

    # ------------------------------------------------------------------
    # save slots
    # ------------------------------------------------------------------
    def slot_path(self, slot: int) -> str:
        return os.path.join(config.SAVES_DIR, config.SAVE_FILENAMES[slot - 1])

    def new_slot_data(self, slot: int) -> Dict[str, Any]:
        """A fresh, empty save for `slot`."""
        return {
            "version": config.VERSION,
            "slot": slot,
            "timestamp": self.now_str(),
            "current_opponent": 0,
            "defeated": [],
            "unlocked_levels": [config.LOCATION_ORDER[0]],
            "selected_character": "default",
            "completion": {},
            "calibration": self.settings.get("calibration"),
            "settings": dict(self.settings),
        }

    def save_slot(self, slot: int, data: Dict[str, Any]) -> None:
        data["timestamp"] = self.now_str()
        self._write_json(self.slot_path(slot), data)

    def load_slot(self, slot: int) -> Optional[Dict[str, Any]]:
        """Returns the slot dict, or None if missing/corrupted."""
        return self._read_json(self.slot_path(slot))

    def slot_summary(self, slot: int) -> Optional[Dict[str, Any]]:
        """Small metadata blob for the LOAD GAME list (never the whole save)."""
        data = self.load_slot(slot)
        if data is None:
            return None
        index = int(data.get("current_opponent", 0))
        opponent = config.OPPONENT_ORDER[min(index, len(config.OPPONENT_ORDER) - 1)]
        return {
            "slot": slot,
            "exists": True,
            "timestamp": data.get("timestamp", "?"),
            "opponent": config.ENEMIES[opponent]["name"],
            "location": config.LOCATIONS[config.LOCATION_ORDER[
                min(index, len(config.LOCATION_ORDER) - 1)]]["name"],
            "defeated": data.get("defeated", []),
        }

    def slot_progress(self, slot: int) -> Optional[Dict[str, Any]]:
        """Restores a playable progression state from a slot (or None)."""
        return self.load_slot(slot)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def now_str() -> str:
        return time.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _read_json(path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("root is not a dict")
            return data
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, ValueError, OSError):
            log.warning("Save file %s is corrupted; ignoring it.", path)
            return None

    @staticmethod
    def _write_json(path: str, data: Dict[str, Any]) -> bool:
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, path)
            return True
        except OSError:
            log.exception("Could not write save file %s", path)
            return False
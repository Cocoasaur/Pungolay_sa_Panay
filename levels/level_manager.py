"""Level manager: ties a progression state to arena backgrounds and the
intro banner shown at fight start.
"""

from __future__ import annotations

from typing import Dict, Optional

import pygame

import config
from gameplay.progression import Progression
from levels.locations import build_arena_background


class LevelManager:
    def __init__(self, progression: Progression) -> None:
        self.progression = progression
        self._backgrounds: Dict[str, pygame.Surface] = {}

    # ------------------------------------------------------------------
    def background(self, location_id: Optional[str] = None) -> pygame.Surface:
        location_id = location_id or self.progression.location_id
        if location_id not in self._backgrounds:
            self._backgrounds[location_id] = build_arena_background(
                config.LOCATIONS[location_id])
        return self._backgrounds[location_id]

    def intro_banner(self) -> dict:
        """The fight introduction text for the current opponent."""
        return {
            "opponent": self.progression.opponent["name"],
            "title": self.progression.opponent.get("title", ""),
            "location": self.progression.location["name"],
            "subtitle": self.progression.location["subtitle"],
            "round": self.progression.current_opponent + 1,
        }
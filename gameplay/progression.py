"""Game progression: the seven Panay opponents and their locations.

The progression is a simple ordered campaign. Defeating an opponent unlocks
the next fight and its location. This module knows nothing about how fights
play out -- it only tracks where the player is.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import config


class Progression:
    def __init__(self) -> None:
        self.current_opponent = 0
        self.defeated: List[str] = []
        self.unlocked_levels: List[str] = [config.LOCATION_ORDER[0]]
        self.completion: Dict[str, str] = {}

    # ------------------------------------------------------------------
    @property
    def opponent_id(self) -> str:
        return config.OPPONENT_ORDER[self.current_opponent]

    @property
    def opponent(self) -> dict:
        return config.ENEMIES[self.opponent_id]

    @property
    def location_id(self) -> str:
        return config.LOCATION_ORDER[self.current_opponent]

    @property
    def location(self) -> dict:
        return config.LOCATIONS[self.location_id]

    @property
    def is_final_fight(self) -> bool:
        return self.current_opponent >= len(config.OPPONENT_ORDER) - 1

    @property
    def campaign_complete(self) -> bool:
        return len(self.defeated) >= len(config.OPPONENT_ORDER)

    def unlocked_opponents(self) -> List[int]:
        """Indices of all opponents the player may select (progression)."""
        indices = []
        for i, oid in enumerate(config.OPPONENT_ORDER):
            if oid in self.defeated or i <= self.current_opponent:
                indices.append(i)
        return indices

    # ------------------------------------------------------------------
    def record_victory(self) -> None:
        """Mark the current opponent as defeated and advance."""
        oid = self.opponent_id
        if oid not in self.defeated:
            self.defeated.append(oid)
            self.completion[oid] = "won"
        if not self.is_final_fight:
            self.current_opponent += 1
            loc = config.LOCATION_ORDER[self.current_opponent]
            if loc not in self.unlocked_levels:
                self.unlocked_levels.append(loc)

    def record_defeat(self) -> None:
        self.completion[self.opponent_id] = "lost"

    def start_fight(self, index: int) -> None:
        self.current_opponent = max(0, min(index, len(config.OPPONENT_ORDER) - 1))

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_opponent": self.current_opponent,
            "defeated": list(self.defeated),
            "unlocked_levels": list(self.unlocked_levels),
            "completion": dict(self.completion),
        }

    def from_dict(self, data: Optional[Dict[str, Any]]) -> None:
        if not data:
            return
        self.current_opponent = int(data.get("current_opponent", 0))
        self.defeated = list(data.get("defeated", []))
        self.unlocked_levels = list(data.get("unlocked_levels",
                                             [config.LOCATION_ORDER[0]]))
        self.completion = dict(data.get("completion", {}))
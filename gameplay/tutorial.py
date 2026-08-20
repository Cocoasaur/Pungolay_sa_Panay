"""Tutorial for the first fight (Jessie).

A short objective checklist shown during the tutorial fight. Objectives are
fulfilled by real gameplay events, not timers. Once every objective is done
(or Jessie is beaten) the panel disappears.
"""

from __future__ import annotations

from typing import Callable, List

import config


class TutorialManager:
    def __init__(self) -> None:
        self.active = False
        self._checks: List[dict] = []

    # ------------------------------------------------------------------
    def start(self) -> None:
        self.active = True
        self._checks = [
            {"text": "Step into frame / stand neutral", "done": False},
            {"text": "Move left & right", "done": False},
            {"text": "Throw a punch (jab forward!)", "done": False},
            {"text": "Guard (hands up near your face)", "done": False},
            {"text": "Beat Jessie", "done": False},
        ]

    @property
    def all_done(self) -> bool:
        return all(c["done"] for c in self._checks)

    def update(self, tracking, player, enemy) -> None:
        if not self.active:
            return
        checks = self._checks

        # 1) neutral stance: pose present long enough (handled by game)
        if not checks[0]["done"] and tracking.pose_present:
            checks[0]["done"] = True

        if not checks[1]["done"]:
            moved = (abs(tracking.horizontal_position - 0.5) > 0.06)
            if moved:
                checks[1]["done"] = True

        if not checks[2]["done"] and player.state in ("punch_l", "punch_r"):
            checks[2]["done"] = True

        if not checks[3]["done"] and tracking.guard:
            checks[3]["done"] = True

        if not checks[4]["done"] and (enemy.hp < enemy.max_hp or
                                      enemy.is_knocked_down):
            checks[4]["done"] = True

        if self.all_done:
            self.active = False
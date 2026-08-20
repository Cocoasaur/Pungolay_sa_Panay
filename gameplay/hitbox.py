"""Hitbox primitives for combat collision.

Hitboxes live in arena pixel space. Attack hitboxes carry a unique attack id
so the combat system can guarantee a single damage application per punch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Hitbox:
    x: float
    y: float          # y of the TOP of the box
    w: float
    h: float
    owner: str        # "player" | "enemy"
    attack_id: Optional[int] = None
    damage: float = 0.0
    knockback: float = 0.0

    def collides(self, other: "Hitbox") -> bool:
        return (self.x < other.x + other.w and
                self.x + self.w > other.x and
                self.y < other.y + other.h and
                self.y + self.h > other.y)

    def center(self) -> tuple:
        return (self.x + self.w / 2, self.y + self.h / 2)
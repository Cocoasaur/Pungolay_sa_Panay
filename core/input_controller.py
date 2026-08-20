"""Keyboard fallback controller.

Produces the exact same TrackingData abstraction as the camera pipeline so
the game is fully playable (and debuggable) without a webcam.
"""

from __future__ import annotations

import pygame

import config
from core.tracking import TrackingData


class KeyboardInput:
    """Reads pygame keys and synthesizes TrackingData."""

    def __init__(self) -> None:
        self._position = 0.5
        self._speed = 0.75          # fraction of arena width per second
        self._left_punch_edge = False
        self._right_punch_edge = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = pygame.key.name(event.key)
        if key == "j":
            self._left_punch_edge = True
        elif key == "k":
            self._right_punch_edge = True

    def update(self, dt: float) -> TrackingData:
        keys = pygame.key.get_pressed()

        def is_down(*names: str) -> bool:
            for n in names:
                if keys[pygame.key.key_code(n)]:
                    return True
            return False

        left = is_down(config.KEYS["left"][0], config.KEYS["left"][1])
        right = is_down(config.KEYS["right"][0], config.KEYS["right"][1])
        guard = is_down(config.KEYS["guard"])

        if left and not right:
            self._position -= self._speed * dt
        elif right and not left:
            self._position += self._speed * dt
        self._position = max(0.0, min(1.0, self._position))

        data = TrackingData(
            present=True,
            horizontal_position=self._position,
            left_punch=self._left_punch_edge,
            right_punch=self._right_punch_edge,
            guard=guard,
            hands_up=guard,          # SPACE doubles as the get-up gesture
            distance_ratio=1.0,
            distance_level="MEDIUM",
            player_scale=1.0,
            body_confidence=1.0,
            pose_present=True,
        )
        self._left_punch_edge = False
        self._right_punch_edge = False
        return data
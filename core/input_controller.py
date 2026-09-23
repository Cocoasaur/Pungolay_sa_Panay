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
        self._left_down_time = 0.0
        self._right_down_time = 0.0
        
        self._left_punch_req = False
        self._right_punch_req = False
        self._left_haymaker_req = False
        self._right_haymaker_req = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            key = pygame.key.name(event.key)
            if key == "j":
                if self._left_down_time >= config.HAYMAKER_CHARGE_TIME:
                    self._left_haymaker_req = True
                else:
                    self._left_punch_req = True
                self._left_down_time = 0.0
            elif key == "k":
                if self._right_down_time >= config.HAYMAKER_CHARGE_TIME:
                    self._right_haymaker_req = True
                else:
                    self._right_punch_req = True
                self._right_down_time = 0.0

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
        j_down = keys[pygame.key.key_code("j")]
        k_down = keys[pygame.key.key_code("k")]
        
        if j_down:
            self._left_down_time += dt
        else:
            self._left_down_time = 0.0
            
        if k_down:
            self._right_down_time += dt
        else:
            self._right_down_time = 0.0

        if left and not right:
            self._position -= self._speed * dt
        elif right and not left:
            self._position += self._speed * dt
        self._position = max(0.0, min(1.0, self._position))
        
        charge_prog = 0.0
        is_charging = False
        is_charged = False
        
        if j_down or k_down:
            max_down = max(self._left_down_time, self._right_down_time)
            is_charging = True
            charge_prog = min(1.0, max_down / config.HAYMAKER_CHARGE_TIME)
            is_charged = max_down >= config.HAYMAKER_CHARGE_TIME

        data = TrackingData(
            present=True,
            horizontal_position=self._position,
            left_punch=self._left_punch_req,
            right_punch=self._right_punch_req,
            left_haymaker=self._left_haymaker_req,
            right_haymaker=self._right_haymaker_req,
            is_charging=is_charging,
            is_charged=is_charged,
            charge_progress=charge_prog,
            guard=guard,
            hands_up=guard,          # SPACE doubles as the get-up gesture
            distance_ratio=1.0,
            distance_level="MEDIUM",
            player_scale=1.0,
            body_confidence=1.0,
            pose_present=True,
        )
        self._left_punch_req = False
        self._right_punch_req = False
        self._left_haymaker_req = False
        self._right_haymaker_req = False
        return data

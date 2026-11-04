"""Keyboard input with a stored, gameplay-owned charge completion event."""

from __future__ import annotations
import pygame
import config
from core.tracking import TrackingData


class KeyboardInput:
    def __init__(self):
        self._position = config.DEPTH_NEUTRAL_HP
        self._speed = 0.75
        self._holds = {"j": 0.0, "k": 0.0}
        self._completed = set()
        self._requests = set()

    def handle_event(self, event):
        if event.type != pygame.KEYUP:
            return
        key = pygame.key.name(event.key)
        if key in self._holds:
            if key not in self._completed:
                self._requests.add(key)
            self._holds[key] = 0.0
            self._completed.discard(key)

    def update(self, dt):
        keys = pygame.key.get_pressed()

        def down(name):
            return bool(keys[pygame.key.key_code(name)])

        left = any(down(k) for k in config.KEYS["left"])
        right = any(down(k) for k in config.KEYS["right"])
        self._position = max(
            0.0, min(1.0, self._position + (int(right) - int(left)) * self._speed * dt)
        )
        completed = False
        progress = 0.0
        charging = False
        for key in self._holds:
            if down(key):
                charging = True
                self._holds[key] += dt
                progress = max(progress, self._holds[key] / config.HAYMAKER_CHARGE_TIME)
                if self._holds[key] >= config.HAYMAKER_CHARGE_TIME and key not in self._completed:
                    self._completed.add(key)
                    completed = True
            elif key not in self._requests:
                self._holds[key] = 0.0
                self._completed.discard(key)
        result = TrackingData(
            present=True,
            horizontal_position=self._position,
            left_punch="j" in self._requests,
            right_punch="k" in self._requests,
            charge_completed=completed,
            is_charging=charging,
            charge_progress=min(1.0, progress),
            guard=down(config.KEYS["guard"]),
            hands_up=down(config.KEYS["get_up"]),
            body_confidence=1.0,
            pose_present=True,
        )
        self._requests.clear()
        return result

    def reset(self, position=None):
        self.__init__()
        if position is not None:
            self._position = position

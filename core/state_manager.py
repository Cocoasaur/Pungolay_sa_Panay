"""Centralized game-state manager.

Scenes are lightweight classes with handle_event / update / draw. The manager
keeps a stack so pause menus can sit on top of gameplay and pop back cleanly.
"""

from __future__ import annotations

from typing import Optional, List

import pygame


class Scene:
    """Base class for every screen (menu, calibration, gameplay, ...)."""

    name = "scene"
    transparent = False

    def __init__(self, game: "Game") -> None:  # noqa: F821 (type name)
        self.game = game

    # -- lifecycle --------------------------------------------------------
    def enter(self) -> None:
        """Called when the scene becomes the top of the stack."""

    def exit(self) -> None:
        """Called when the scene is popped or replaced."""

    # -- per-frame --------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


class StateManager:
    def __init__(self) -> None:
        self._stack: List[Scene] = []

    @property
    def current(self) -> Optional[Scene]:
        return self._stack[-1] if self._stack else None

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)
        scene.enter()

    def pop(self) -> Optional[Scene]:
        scene = self._stack.pop() if self._stack else None
        if scene is not None:
            scene.exit()
        return scene

    def replace(self, scene: Scene) -> None:
        """Pop everything and make `scene` the only state."""
        while self._stack:
            self._stack.pop().exit()
        self._stack.append(scene)
        scene.enter()

    def clear(self) -> None:
        while self._stack:
            self._stack.pop().exit()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.current is not None:
            self.current.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current is not None:
            self.current.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        # draw every scene below the top one too (pause over gameplay etc.)
        start = 0
        for i in range(len(self._stack)-1, -1, -1):
            if not self._stack[i].transparent:
                start = i
                break
        for scene in self._stack[start:]:
            scene.draw(surface)

    def return_to(self, scene):
        if scene in self._stack:
            while self.current is not scene:
                self.pop()
            return True
        return False
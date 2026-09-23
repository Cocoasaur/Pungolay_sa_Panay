"""Pause menu: an overlay pushed on top of the gameplay scene."""

from __future__ import annotations

import pygame

import config
from core.state_manager import Scene

C = config.COLORS

PAUSE_ITEMS = ["RESUME", "RETRY FIGHT", "LEVEL SELECT", "SETTINGS",
               "MAIN MENU", "QUIT"]


class PauseMenu(Scene):
    name = "pause"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.fonts = game.fonts
        self.selected = 0
        self._rects = []
        self._plain = [self.fonts["medium"].render(i, True, C["text"])
                       for i in PAUSE_ITEMS]
        self._hover = [self.fonts["medium"].render(i, True, C["title_white"])
                       for i in PAUSE_ITEMS]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("up", "w"):
                self.selected = (self.selected - 1) % len(PAUSE_ITEMS)
                self.game.audio.play("menu_move")
            elif key in ("down", "s"):
                self.selected = (self.selected + 1) % len(PAUSE_ITEMS)
                self.game.audio.play("menu_move")
            elif key in ("return", "space"):
                self._activate()
            elif key == "escape":
                self.game.audio.play("menu_move")
                self.game.states.pop()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self._activate()

    def _activate(self) -> None:
        item = PAUSE_ITEMS[self.selected]
        self.game.audio.play("menu_select")
        if item == "RESUME":
            self.game.states.pop()
        elif item == "RETRY FIGHT":
            self.game.retry_fight()
        elif item == "LEVEL SELECT":
            self.game.show_level_select()
        elif item == "SETTINGS":
            self.game.show_settings(back_to="pause")
        elif item == "MAIN MENU":
            self.game.to_main_menu()
        elif item == "QUIT":
            self.game.quit()

    def draw(self, surface: pygame.Surface) -> None:
        # dim the arena underneath
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))

        title = self.fonts["big"].render("PAUSED", True, C["title_white"])
        surface.blit(title, title.get_rect(center=(config.BASE_WIDTH // 2, 150)))

        self._rects = []
        y = 250
        for i, item in enumerate(PAUSE_ITEMS):
            rect = pygame.Rect(config.BASE_WIDTH // 2 - 130, y - 12, 260, 44)
            self._rects.append(rect)
            if i == self.selected:
                pygame.draw.rect(surface, (52, 46, 40, 200), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x, rect.y, 4, 44))
                surf = self._hover[i]
            else:
                surf = self._plain[i]
            surface.blit(surf, surf.get_rect(center=(config.BASE_WIDTH // 2, y + 10)))
            y += 52

        hint = self.fonts["tiny"].render("ESC TO RESUME", True, C["text_faint"])
        surface.blit(hint, hint.get_rect(center=(config.BASE_WIDTH // 2, 620)))
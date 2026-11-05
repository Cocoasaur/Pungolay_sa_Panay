"""Boxing-poster menu with contained live typography and animated athletes."""

import pygame
import config
from core.state_manager import Scene
from ui.backgrounds import build_menu_background
from ui.fonts import cached_text, render_spaced
from ui.sprites import draw_boxer
from ui import theme


class MainMenu(Scene):
    name = "main_menu"

    def __init__(self, game):
        super().__init__(game)
        self.fonts = game.fonts
        self.selected = 0
        self.anim_t = 0
        self.items = list(config.MENU_ITEMS)
        self._item_rects = [pygame.Rect(96, 340 + i * 64, 416, 52) for i in range(len(self.items))]
        self.panel_rect = pygame.Rect(64, 64, 480, 592)
        self.title_bounds = pygame.Rect(96, 96, 416, 184)
        self.background = build_menu_background()
        self.menu_overlay = None
        self.title_surf = render_spaced(
            "PUNGOLAY SA",
            theme.fitted("PUNGOLAY SA", 416, 25, True, 3),
            config.COLORS["title_white"],
            3,
        )
        self.subtitle_surf = render_spaced(
            "PANAY", theme.fitted("PANAY", 416, 104, True, 6), config.COLORS["title_white"], 6
        )
        self._shade = pygame.Surface((1280, 720), pygame.SRCALPHA)
        self._shade.fill((9, 8, 6, 48))

    def enter(self):
        self.selected = 0
        from ui.animation import prewarm_pair

        prewarm_pair(("player", -1), ("jessie", 1))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.items)
                self.game.audio.play("menu_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.items)
                self.game.audio.play("menu_move")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._activate(self.selected)
            elif event.key == pygame.K_ESCAPE:
                self.game.quit()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(event.pos):
                    self._activate(i)
                    break

    def _activate(self, index):
        self.game.audio.play("menu_select")
        item = self.items[index]
        if item == "NEW GAME":
            self.game.start_new_game()
        elif item == "LOAD GAME":
            self.game.show_load_game()
        elif item == "SETTINGS":
            self.game.show_settings(back_to=self.name)
        elif item == "QUIT":
            self.game.quit()

    def update(self, dt):
        self.anim_t += dt

    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        surface.blit(self._shade, (0, 0))
        theme.panel(surface, self.panel_rect, True)
        surface.blit(self.title_surf, (96, 100))
        surface.blit(self.subtitle_surf, (96, 142))
        pygame.draw.rect(surface, config.COLORS["accent_red"], (96, 262, 96, 5))
        theme.text(surface, self.fonts, "WEB-CAM BOXING / WESTERN VISAYAS", (96, 286))
        for i, (item, rect) in enumerate(zip(self.items, self._item_rects)):
            theme.button(surface, rect, item, self.selected == i, primary=i == 0)
        theme.text(surface, self.fonts, "ARROWS + ENTER  /  MOUSE", (96, 620), size="tiny")
        version = cached_text(
            self.fonts["tiny"], "VERSION " + config.VERSION, config.COLORS["title_white"]
        )
        surface.blit(version, (1248 - version.get_width(), 28))
        draw_boxer(
            surface,
            820,
            config.GROUND_Y,
            1,
            "idle",
            self.anim_t + 1.1,
            1,
            config.COLORS["trunks_enemy"],
            fighter_id="jessie",
        )
        draw_boxer(
            surface,
            1080,
            config.GROUND_Y,
            -1,
            "idle",
            self.anim_t,
            1,
            config.COLORS["trunks_player"],
            fighter_id="player",
        )

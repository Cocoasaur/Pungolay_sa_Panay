"""The main menu: the game's visual identity.

Layout follows the reference: dark charcoal frame, industrial gym backdrop,
"PUNGOLAY SA" over a much larger "PANAY", a menu panel on the left, the two
boxers on the right, VERSION in the upper-right corner. Supports mouse hover/
click and keyboard navigation (arrows + Enter, Escape quits).
"""

from __future__ import annotations

import os

import pygame

import config
from core.state_manager import Scene
from ui.fonts import render_spaced
from ui.sprites import draw_boxer

C = config.COLORS


class MainMenu(Scene):
    name = "main_menu"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.fonts = game.fonts
        self.selected = 0
        self.anim_t = 0.0
        self.background = None
        self.title_surf = None
        self.subtitle_surf = None
        self.version_surf = None
        self.menu_overlay = None
        self.items = list(config.MENU_ITEMS)
        self._item_rects = []
        self._build_static()

    # ------------------------------------------------------------------
    def _build_static(self) -> None:
        from ui.backgrounds import build_menu_background
        self.background = build_menu_background()
        if (not os.path.isfile(config.MENU_BACKGROUND_PATH)
                and os.path.isfile(config.MENU_IMAGE_PATH)):
            image = pygame.image.load(config.MENU_IMAGE_PATH).convert_alpha()
            if image.get_size() != (config.BASE_WIDTH, config.BASE_HEIGHT):
                image = pygame.transform.smoothscale(
                    image, (config.BASE_WIDTH, config.BASE_HEIGHT))
            self.menu_overlay = image
        f = self.fonts

        # title: "PUNGOLAY SA" small, "PANAY" huge below it
        self.title_surf = render_spaced("PUNGOLAY SA", f["medium"],
                                        C["title_gray"], spacing=8)
        self.subtitle_surf = render_spaced("PANAY", f["huge"],
                                           C["title_white"], spacing=14)
        self.version_surf = f["tiny"].render(f"VERSION {config.VERSION}",
                                             True, C["text_faint"])
        self.tagline_surf = f["tiny"].render(
            "WEB-CAM BOXING  -  WESTERN VISAYAS", True, C["text_faint"])

        # pre-render menu item labels in both states
        self._item_plain = [f["medium"].render(item, True, C["text"])
                            for item in self.items]
        self._item_hover = [f["medium"].render(item, True, C["title_white"])
                            for item in self.items]

    def enter(self) -> None:
        self.selected = 0

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key in ("up", "w"):
                self.selected = (self.selected - 1) % len(self.items)
                self.game.audio.play("menu_move")
            elif key in ("down", "s"):
                self.selected = (self.selected + 1) % len(self.items)
                self.game.audio.play("menu_move")
            elif key in ("return", "kp_enter", "space"):
                self._activate(self.selected)
            elif key == "escape":
                self.game.quit()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(event.pos):
                    if i != self.selected:
                        self.selected = i
                        self.game.audio.play("menu_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._item_rects):
                if rect.collidepoint(event.pos):
                    self._activate(i)

    def _activate(self, index: int) -> None:
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

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.anim_t += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        if self.menu_overlay is not None:
            surface.blit(self.menu_overlay, (0, 0))

        # ---- title block (left) ---------------------------------------
        surface.blit(self.title_surf, (128, 110))
        surface.blit(self.subtitle_surf, (120, 138))
        # accent line under the title
        pygame.draw.rect(surface, C["accent_red"], (128, 330, 120, 4))
        surface.blit(self.tagline_surf, (128, 344))

        # ---- version (upper right) ------------------------------------
        surface.blit(self.version_surf,
                     (config.BASE_WIDTH - 22 - self.version_surf.get_width(), 26))

        # ---- menu panel (left) ----------------------------------------
        panel_x, panel_y, panel_w = 128, 400, 330
        panel = pygame.Surface((panel_w, 250), pygame.SRCALPHA)
        panel.fill(C["panel"])
        surface.blit(panel, (panel_x, panel_y))
        pygame.draw.rect(surface, C["border"], (panel_x, panel_y, panel_w, 250), 1)

        self._item_rects = []
        y = panel_y + 34
        for i, item in enumerate(self.items):
            hover = i == self.selected
            rect = pygame.Rect(panel_x + 22, y - 12, panel_w - 44, 44)
            self._item_rects.append(rect)
            if hover:
                pygame.draw.rect(surface, (52, 46, 40, 160), rect)
                pygame.draw.rect(surface, C["accent_red"], (rect.x - 22, rect.y, 4, 44))
                surf = self._item_hover[i]
            else:
                surf = self._item_plain[i]
            surface.blit(surf, (rect.x + 10, y))
            y += 50

        # ---- boxers (right side) --------------------------------------
        self._draw_boxers(surface)

        # ---- controls hint (bottom) ------------------------------------
        hint = self.fonts["tiny"].render(
            "ARROWS / ENTER  -  MOUSE", True, C["text_faint"])
        surface.blit(hint, (22, config.BASE_HEIGHT - 34))

    # ------------------------------------------------------------------
    def _draw_boxers(self, surface: pygame.Surface) -> None:
        """Player and enemy placeholder boxers facing each other."""
        enemy_x = config.BASE_WIDTH - 300
        player_x = config.BASE_WIDTH - 130
        foot_y = 690
        t = self.anim_t

        # subtle warm glow behind the fighters
        glow = pygame.Surface((380, 220), pygame.SRCALPHA)
        for r in range(190, 0, -8):
            alpha = int(6 * (1 - r / 190))
            pygame.draw.ellipse(glow, C["warm_glow"] + (alpha,),
                                (190 - r, 110 - r * 0.6, r * 2, r * 1.2))
        surface.blit(glow, (enemy_x - 230, foot_y - 250))

        # enemy faces the player (facing right), player faces the enemy
        draw_boxer(surface, enemy_x, foot_y, facing=1, state="idle",
                   anim_t=t + 1.3, scale=1.05,
                   trunks_color=config.ENEMIES["jessie"].get("trunks"),
                   fighter_id="jessie")
        draw_boxer(surface, player_x, foot_y, facing=-1, state="idle",
                   anim_t=t, scale=1.05, trunks_color=C["trunks_player"],
                   fighter_id="player")
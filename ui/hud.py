"""In-game HUD: health/stamina bars, names, distance chip, camera status."""

from __future__ import annotations

import pygame

import config
from gameplay.enemy import Enemy
from gameplay.player import Player

C = config.COLORS


class HUD:
    def __init__(self, fonts: dict) -> None:
        self.fonts = fonts

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, player: Player, enemy: Enemy,
             distance_level: str, camera_status: str, pose_present: bool,
             tracking_lost: bool, countdown: str = "", fight_over: bool = False,
             time_ms: int = 0) -> None:
        small = self.fonts["small"]
        medium = self.fonts["medium"]

        # ---- player side (left) ---------------------------------------
        self._draw_bar(surface, 30, 26, 360, 20, player.hp, player.max_hp,
                       C["hp_red"], C["hp_red_dark"],
                       "PLAYER", f"{int(player.hp)}", small)
        self._draw_bar(surface, 30, 52, 220, 10, player.stamina, player.max_stamina,
                       C["stamina_amber"], C["stamina_empty"], "", "", small)

        # ---- enemy side (right) ---------------------------------------
        self._draw_bar(surface, config.BASE_WIDTH - 390, 26, 360, 20,
                       enemy.hp, enemy.max_hp, C["hp_red"], C["hp_red_dark"],
                       enemy.name.upper(), f"{int(enemy.hp)}", small)
        self._draw_bar(surface, config.BASE_WIDTH - 250, 52, 220, 10,
                       enemy.hp, enemy.max_hp, C["stamina_amber"],
                       C["stamina_empty"], "", "", small)

        # ---- center: opponent / location ------------------------------
        center = medium.render(f"{enemy.name}  -  {enemy.title.upper()}",
                               True, C["text"])
        surface.blit(center, center.get_rect(midtop=(config.BASE_WIDTH // 2, 28)))

        # ---- distance chip --------------------------------------------
        chip_color = {"CLOSE": C["accent_red_bright"],
                      "MEDIUM": C["warn_yellow"],
                      "FAR": C["text_dim"]}.get(distance_level, C["text_dim"])
        chip = small.render(f"DISTANCE: {distance_level}", True, chip_color)
        surface.blit(chip, (config.BASE_WIDTH // 2 - chip.get_width() // 2,
                            config.BASE_HEIGHT - 30))

        # ---- camera / tracking status ---------------------------------
        status_color = C["ok_green"] if pose_present else C["warn_yellow"]
        status = small.render(f"CAMERA: {camera_status}", True, status_color)
        surface.blit(status, (24, config.BASE_HEIGHT - 30))
        if tracking_lost:
            hint = small.render("STEP INTO THE CAMERA FRAME", True,
                                C["accent_red_bright"])
            surface.blit(hint, hint.get_rect(center=(config.BASE_WIDTH // 2,
                                                     config.BASE_HEIGHT - 64)))

        # ---- knockdown countdown --------------------------------------
        if countdown:
            big = self.fonts["big"]
            label = big.render(countdown, True, C["title_white"])
            surface.blit(label, label.get_rect(center=(config.BASE_WIDTH // 2,
                                                       config.BASE_HEIGHT // 2 - 40)))

    # ------------------------------------------------------------------
    @staticmethod
    def _draw_bar(surface, x, y, w, h, value, max_value, color, bg,
                  label, value_text, font) -> None:
        pygame.draw.rect(surface, bg, (x, y, w, h))
        if max_value > 0:
            fill = max(0, min(1.0, value / max_value))
            pygame.draw.rect(surface, color, (x, y, int(w * fill), h))
        pygame.draw.rect(surface, C["border"], (x, y, w, h), 1)
        if label:
            label_surf = font.render(label, True, C["text"])
            surface.blit(label_surf, (x, y - 18))
        if value_text:
            text = font.render(value_text, True, C["title_white"])
            surface.blit(text, text.get_rect(midright=(x + w - 6, y + h // 2)))
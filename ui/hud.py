"""In-game HUD: health/stamina bars, names, distance chip, camera status."""

from __future__ import annotations

import os

import pygame

import config
from ui.assets import load_image
from gameplay.enemy import Enemy
from gameplay.player import Player

C = config.COLORS


class HUD:
    def __init__(self, fonts: dict) -> None:
        self.fonts = fonts
        self.overlay = None
        if os.path.isfile(config.HUD_IMAGE_PATH):
            image = load_image(config.HUD_IMAGE_PATH, (config.BASE_WIDTH, config.BASE_HEIGHT))
            if image is not None and image.get_size() != (config.BASE_WIDTH, config.BASE_HEIGHT):
                image = pygame.transform.smoothscale(
                    image, (config.BASE_WIDTH, config.BASE_HEIGHT))
            self.overlay = image

    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, player: Player, enemy: Enemy,
             distance_level: str, camera_status: str, pose_present: bool,
             tracking_lost: bool, countdown: str = "", fight_over: bool = False,
             time_ms: int = 0, tracking=None) -> None:
        if self.overlay is not None:
            surface.blit(self.overlay, (0, 0))

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
                       enemy.name.upper(), f"{int(enemy.hp)}", small,
                       label_align="right")
        self._draw_bar(surface, config.BASE_WIDTH - 250, 52, 220, 10,
                       enemy.hp, enemy.max_hp, C["stamina_amber"],
                       C["stamina_empty"], "", "", small)

        # ---- center: opponent / location ------------------------------
        center = medium.render(f"{enemy.name}  -  {enemy.title.upper()}",
                               True, C["text"])
        center_rect = center.get_rect(midtop=(config.BASE_WIDTH // 2, 28))
        name_panel = center_rect.inflate(24, 12)
        pygame.draw.rect(surface, (12, 11, 10, 225), name_panel,
                         border_radius=8)
        pygame.draw.rect(surface, C["warm_glow"], name_panel, width=2,
                         border_radius=8)
        surface.blit(center, center_rect)

        # ---- charging indicator ---------------------------------------
        if (player.is_charging or player.ability_ready) and not fight_over and player.state != "ko":
            charge_w = 200
            charge_h = 14
            cx = config.BASE_WIDTH // 2 - charge_w // 2
            cy = 70
            pygame.draw.rect(surface, C["stamina_empty"], (cx, cy, charge_w, charge_h))
            
            fill_w = int(charge_w * player.charge_progress)
            color = C["warm_glow"] if player.ability_ready else C["stamina_amber"]
            
            if fill_w > 0:
                pygame.draw.rect(surface, color, (cx, cy, fill_w, charge_h))
            pygame.draw.rect(surface, C["border"], (cx, cy, charge_w, charge_h), 1)
            
            label_text = "HAYMAKER READY!" if player.ability_ready else "CHARGING..."
            label_surf = small.render(label_text, True, color)
            surface.blit(label_surf, label_surf.get_rect(midbottom=(config.BASE_WIDTH // 2, cy - 4)))

        if not fight_over and player.state in ("guard", "punch_l", "punch_r"):
            feedback = "BLOCK" if player.guarding else "HAYMAKER!" if player.is_haymaker_punch else "LEFT PUNCH" if player.state == "punch_l" else "RIGHT PUNCH"
            label = small.render(feedback, True, C["title_white"])
            panel = label.get_rect(midbottom=(int(player.x), int(config.GROUND_Y-player.body_h*player.scale-12))).inflate(16,8)
            pygame.draw.rect(surface, (20,18,16), panel, border_radius=4)
            surface.blit(label,label.get_rect(center=panel.center))
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
                  label, value_text, font, label_align="left") -> None:
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surface, (10, 9, 8), rect.inflate(6, 6),
                         border_radius=5)
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        if max_value > 0:
            fill = max(0, min(1.0, value / max_value))
            inner = rect.inflate(-4, -4)
            fill_rect = pygame.Rect(inner.x, inner.y,
                                    int(inner.width * fill), inner.height)
            if fill_rect.width > 0:
                pygame.draw.rect(surface, color, fill_rect, border_radius=2)
        pygame.draw.rect(surface, C["border"], rect, width=3, border_radius=4)
        pygame.draw.line(surface, (205, 176, 132),
                         (x + 5, y + 1), (x + w - 6, y + 1), 1)
        if label:
            label_surf = font.render(label, True, C["text"])
            pill_w = label_surf.get_width() + 16
            pill_h = label_surf.get_height() + 4
            pill_x = (x + w - pill_w) if label_align == "right" else x
            pill_y = y - pill_h - 3
            pill = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
            pygame.draw.rect(surface, (18, 16, 14), pill, border_radius=6)
            pygame.draw.rect(surface, C["accent_red"], pill, width=1,
                             border_radius=6)
            surface.blit(label_surf, label_surf.get_rect(center=pill.center))
        if value_text:
            text = font.render(value_text, True, C["title_white"])
            surface.blit(text, text.get_rect(midright=(x + w - 6, y + h // 2)))

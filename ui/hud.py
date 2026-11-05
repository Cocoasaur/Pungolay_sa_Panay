"""Compact fight overlays that leave the arena and fighters in view."""

from functools import lru_cache

import pygame
import config
from ui import theme
from ui.fonts import cached_text

C = config.COLORS


@lru_cache(maxsize=24)
def _panel_image(size, accent=None):
    """Cache translucent backplates; never dim the whole arena for the HUD."""
    image = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(image, (23, 21, 18, 222), image.get_rect(), border_radius=5)
    pygame.draw.rect(image, (125, 110, 88, 160), image.get_rect(), 1, border_radius=5)
    if accent:
        pygame.draw.rect(image, accent, (0, 8, 3, size[1] - 16), border_radius=1)
    return image


def overlay_panel(surface, rect, accent=None):
    surface.blit(_panel_image(rect.size, accent), rect)


def compact_control(surface, rect, label):
    """Small camera toolbar control; its complete visible area is clickable."""
    overlay_panel(surface, rect)
    font = theme.fitted(label, rect.w - 12, 13, True)
    image = cached_text(font, label, C["title_white"])
    surface.blit(image, image.get_rect(center=rect.center))


class HUD:
    HEALTH_LEFT = pygame.Rect(20, 18, 304, 68)
    HEALTH_RIGHT = pygame.Rect(956, 18, 304, 68)
    CHARGE = pygame.Rect(440, 650, 400, 52)
    WARNING = pygame.Rect(20, 650, 380, 52)

    def __init__(self, fonts):
        self.fonts = fonts

    def draw(
        self,
        surface,
        player,
        enemy,
        distance_level="MEDIUM",
        camera_status="",
        pose_present=False,
        tracking_lost=False,
        countdown="",
        fight_over=False,
        time_ms=0,
        tracking=None,
    ):
        for rect, fighter, name in (
            (self.HEALTH_LEFT, player, "PLAYER"),
            (self.HEALTH_RIGHT, enemy, enemy.name.upper()),
        ):
            overlay_panel(surface, rect)
            self._label(surface, name, (rect.x + 12, rect.y + 8), 238, 16, bold=True)
            hp = cached_text(self.fonts["small"], str(max(0, round(fighter.hp))), C["title_white"])
            surface.blit(hp, hp.get_rect(topright=(rect.right - 12, rect.y + 8)))
            self._bar(
                surface,
                pygame.Rect(rect.x + 12, rect.y + 31, 280, 12),
                fighter.hp / fighter.max_hp,
                C["hp_red"],
            )
        self._label(surface, "STAMINA", (32, 69), 60, 12, C["text_dim"])
        self._bar(
            surface,
            pygame.Rect(102, 73, 210, 4),
            player.stamina / player.max_stamina,
            C["stamina_amber"],
        )
        self._label(surface, enemy.title.upper(), (968, 68), 280, 12, C["text_dim"])
        self.charge(
            surface, player, tracking, fight_over, keyboard=camera_status == "KEYBOARD MODE"
        )
        if not fight_over and player.state in ("guard", "punch_l", "punch_r"):
            message = (
                "BLOCK"
                if player.guarding
                else (
                    "HAYMAKER!"
                    if player.is_haymaker_punch
                    else "LEFT PUNCH" if player.state == "punch_l" else "RIGHT PUNCH"
                )
            )
            label = cached_text(self.fonts["small"], message, C["title_white"])
            rect = label.get_rect(
                midbottom=(round(player.x), config.GROUND_Y - config.FIGHTER_BODY_HEIGHT - 12)
            ).inflate(16, 8)
            overlay_panel(surface, rect)
            surface.blit(label, label.get_rect(center=rect.center))

        # Routine HOLDING/MOVING and keyboard status belong in Debug. Only an
        # actionable tracking problem needs a persistent in-fight notice.
        warning = self.tracking_warning(camera_status, tracking_lost, tracking)
        if warning and not fight_over:
            overlay_panel(surface, self.WARNING, C["warn_yellow"])
            self._label(surface, warning[0], (32, 659), 356, 14, C["warn_yellow"], True)
            self._label(surface, warning[1], (32, 680), 356, 12, C["title_white"])
        if countdown:
            label = cached_text(self.fonts["big"], countdown, C["title_white"])
            surface.blit(label, label.get_rect(center=(640, 256)))
            instruction = (
                "BEAT THE COUNT / RAISE BOTH HANDS" if player.is_knocked_down else "OPPONENT DOWN"
            )
            font = theme.fitted(instruction, 400, 16, True)
            image = cached_text(font, instruction, C["title_white"])
            surface.blit(image, image.get_rect(center=(640, 312)))

    @staticmethod
    def tracking_warning(camera_status, tracking_lost, tracking):
        if camera_status == "KEYBOARD MODE":
            return None
        if tracking and tracking.movement_status == "TRACKING LOST":
            if tracking.pose_present:
                return "MOVEMENT PAUSED", "Show both hips / step back into frame"
            return "TRACKING LOST", "Step into view to resume movement"
        if tracking_lost:
            return "TRACKING LOST", "Step into view to resume movement"
        return None

    def charge(self, surface, player, tracking, fight_over=False, keyboard=False):
        if fight_over:
            return
        rect = self.CHARGE
        ready = player.ability_ready
        progress = (
            1 if ready else (tracking.charge_progress if tracking else player.charge_progress)
        )
        active = bool(tracking.is_charging if tracking else player.is_charging)
        side = tracking.charge_side if tracking else ""
        color = (
            C["warm_glow"]
            if ready
            else (
                config.ARM_LEFT_COLOR
                if side == "left"
                else config.ARM_RIGHT_COLOR if side == "right" else C["text_dim"]
            )
        )
        if ready:
            headline = "HAYMAKER READY / NEXT PUNCH 2×"
            hint = "Tap J or K to use" if keyboard else "Left or right punch to use"
        elif active:
            headline = f"{side.upper() + ' ' if side else ''}HAYMAKER / {max(0, 5-progress*5):.1f}s"
            hint = (tracking.charge_hint if tracking else "") or "Hold your glove beside your chest"
        else:
            headline = "HAYMAKER / HOLD 5s"
            hint = (
                tracking.charge_hint if tracking else ""
            ) or "Pull one glove back beside your chest"
        if keyboard and not ready:
            hint = (
                "Keep holding J or K; release when ready"
                if active
                else "Hold J or K for 5s, then tap either to punch"
            )
        overlay_panel(surface, rect, color if active or ready else None)
        self._label(surface, headline, (rect.x + 12, rect.y + 7), 376, 15, color, True)
        self._label(surface, hint, (rect.x + 12, rect.y + 27), 376, 12, C["title_white"])
        if active or ready:
            self._bar(surface, pygame.Rect(rect.x + 12, rect.bottom - 7, 376, 3), progress, color)

    @staticmethod
    def _label(surface, text, pos, width, size, color=None, bold=False):
        font = theme.fitted(text, width, size, bold)
        surface.blit(cached_text(font, text, color or C["title_white"]), pos)

    @staticmethod
    def _bar(surface, rect, value, color):
        pygame.draw.rect(surface, (60, 49, 38), rect)
        pygame.draw.rect(
            surface, color, (rect.x, rect.y, round(rect.w * max(0, min(1, value))), rect.h)
        )

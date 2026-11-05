"""Readable boxing scorecard with a persistent, gameplay-owned ability cue."""

import pygame
import config
from ui import theme
from ui.fonts import cached_text

C = config.COLORS


class HUD:
    def __init__(self, fonts):
        self.fonts = fonts
        self.overlay = None

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
        pygame.draw.rect(surface, (23, 21, 18), (0, 0, 1280, 132))
        pygame.draw.line(surface, C["border"], (24, 131), (1256, 131))
        for x, fighter, name in ((32, player, "PLAYER"), (880, enemy, enemy.name.upper())):
            theme.text(surface, self.fonts, name, (x, 14), C["title_white"])
            self._bar(
                surface, pygame.Rect(x, 40, 368, 18), fighter.hp / fighter.max_hp, C["hp_red"]
            )
            theme.text(
                surface, self.fonts, str(max(0, round(fighter.hp))), (x + 332, 16), C["title_white"]
            )
        self._bar(
            surface,
            pygame.Rect(32, 68, 224, 7),
            player.stamina / player.max_stamina,
            C["stamina_amber"],
        )
        theme.text(surface, self.fonts, "STAMINA", (32, 83), size="tiny")
        title = (enemy.name + " / " + enemy.title).upper()
        font = theme.fitted(title, 380, 18, True)
        image = cached_text(font, title, C["title_white"])
        surface.blit(image, image.get_rect(center=(640, 28)))
        self.charge(surface, player, tracking, fight_over)
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
            theme.panel(surface, rect)
            surface.blit(label, label.get_rect(center=rect.center))
        status = (
            "TRACKING LOST / REPOSITION"
            if tracking_lost
            else (
                "KEYBOARD CONTROLS"
                if camera_status == "KEYBOARD MODE"
                else (tracking.movement_status if tracking else camera_status)
            )
        )
        if tracking and tracking.pose_present and tracking.movement_status == "TRACKING LOST":
            status = "SHOW BOTH HIPS / STEP BACK INTO FRAME"
        theme.panel(surface, pygame.Rect(24, 666, 420, 28))
        theme.text(
            surface,
            self.fonts,
            status,
            (36, 673),
            C["warn_yellow"] if tracking_lost else C["text"],
            size="tiny",
        )
        if countdown:
            label = cached_text(self.fonts["big"], countdown, C["title_white"])
            surface.blit(label, label.get_rect(center=(640, 256)))
            theme.text(
                surface,
                self.fonts,
                "BEAT THE COUNT / RAISE BOTH HANDS",
                (468, 304),
                C["title_white"],
            )

    def charge(self, surface, player, tracking, fight_over=False):
        rect = pygame.Rect(448, 56, 384, 64)
        theme.panel(surface, rect)
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
            headline = "HAYMAKER READY — NEXT PUNCH 2×"
            hint = "Your next accepted left or right punch uses it"
        elif active:
            headline = f"{side.upper()} CHARGE / {max(0,5-progress*5):.1f}s"
            hint = tracking.charge_hint if tracking else "Hold your glove beside your chest"
        else:
            headline = "HAYMAKER / HOLD 5 SECONDS"
            hint = "Pull either glove back beside your chest"
        if fight_over:
            headline = "ROUND COMPLETE"
            hint = ""
        font = theme.fitted(headline, 352, 17, True)
        image = cached_text(font, headline, color)
        surface.blit(image, (464, 64))
        self._bar(surface, pygame.Rect(464, 88, 352, 6), progress if active or ready else 0, color)
        font = theme.fitted(hint, 352, 13)
        surface.blit(cached_text(font, hint, C["text_dim"]), (464, 100))

    @staticmethod
    def _bar(surface, rect, value, color):
        pygame.draw.rect(surface, (60, 49, 38), rect)
        pygame.draw.rect(
            surface, color, (rect.x, rect.y, round(rect.w * max(0, min(1, value))), rect.h)
        )

"""The FightScene: one boxing match between the player and an enemy.

Owns the two fighters, the enemy AI, combat resolution, HUD, intro banner,
tutorial panel and the fight-end transition. All camera work stays inside
the Game shell -- this scene only consumes TrackingData.
"""

from __future__ import annotations

import time
from typing import Optional

import pygame

import config
from core.state_manager import Scene
from core.tracking import TrackingData
from gameplay.ai import EnemyAI
from gameplay.combat import CombatManager
from gameplay.enemy import Enemy
from gameplay.player import Player
from gameplay.tutorial import TutorialManager
from ui.hud import HUD
from ui.sprites import draw_boxer

C = config.COLORS

FIGHT_OVER_DELAY = 1.6     # seconds the KO pose is shown before the screen
INTRO_BANNER_TIME = 2.8


class FightScene(Scene):
    name = "gameplay"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.hud = HUD(game.fonts)
        self.combat = CombatManager(game.events)
        self.tutorial = TutorialManager()
        self.player: Optional[Player] = None
        self.enemy: Optional[Enemy] = None
        self.ai: Optional[EnemyAI] = None
        self._reset_for_opponent()
        self.intro_banner: Optional[dict] = None
        self.intro_timer = 0.0
        self._was_punching = False
        self._was_enemy_attacking = False
        self._over_timer = 0.0

    # ------------------------------------------------------------------
    def _reset_for_opponent(self) -> None:
        game = self.game
        self.player = Player(x=config.BASE_WIDTH // 2 - 180)
        # Keep camera tracking aligned with this spawn instead of carrying a
        # target from a menu, calibration screen, or the preceding opponent.
        game.reset_tracking_position()
        self.enemy = Enemy(game.progression.opponent,
                           x=config.BASE_WIDTH // 2 + 180)
        self.ai = EnemyAI(self.enemy, self.player)
        self.combat.reset()
        self.intro_banner = game.level_manager.intro_banner()
        self.intro_timer = INTRO_BANNER_TIME
        self._over_timer = 0.0
        self._was_punching = False
        self._was_enemy_attacking = False

        is_tutorial = game.progression.current_opponent == 0
        if is_tutorial:
            self.tutorial.start()
        else:
            self.tutorial.active = False

    def enter(self) -> None:
        self._reset_for_opponent()

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key == "escape":
                if self.combat.fight_over:
                    return
                self.game.audio.play("menu_move")
                from ui.pause_menu import PauseMenu
                self.game.states.push(PauseMenu(self.game))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        game = self.game
        now = time.monotonic()
        tracking = game.get_current_tracking()

        if self.intro_timer > 0:
            self.intro_timer -= dt
            return

        # fighters freeze during the hit-stop beat
        if self.combat.hitstop > 0:
            self.combat.update(dt, self.player, self.enemy)
            return

        # -- fighters ----------------------------------------------------
        self.player.update(dt, tracking, now)
        self.enemy.update(dt, now)
        if self.ai is not None and not self.combat.fight_over:
            self.ai.update(dt, self.player.state in ("punch_l", "punch_r"))

        # -- combat ------------------------------------------------------
        self.combat.resolve(self.player, self.enemy, dt)
        self.combat.update(dt, self.player, self.enemy)

        # -- sound hooks -------------------------------------------------
        if self.player.state in ("punch_l", "punch_r") and not self._was_punching:
            game.audio.play("punch")
        self._was_punching = self.player.state in ("punch_l", "punch_r")
        if self.enemy.is_attacking and not self._was_enemy_attacking:
            game.audio.play("punch", volume=0.6)
        self._was_enemy_attacking = self.enemy.is_attacking

        # -- tutorial ----------------------------------------------------
        if self.tutorial.active:
            self.tutorial.update(tracking, self.player, self.enemy)

        # -- fight end ---------------------------------------------------
        if self.combat.fight_over and not self.player.ko and not self.enemy.ko:
            # someone got up from the count; the fight continues
            pass
        if self.combat.fight_over:
            self._over_timer += dt
            if self._over_timer >= FIGHT_OVER_DELAY:
                self._finish_fight()

    def _finish_fight(self) -> None:
        game = self.game
        if self.combat.winner == "player":
            game.progression.record_victory()
            game.save_current_progress()
            from ui.screens import VictoryScreen
            game.states.push(VictoryScreen(game))
        else:
            game.progression.record_defeat()
            from ui.screens import DefeatScreen
            game.states.push(DefeatScreen(game))

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        game = self.game
        surface.blit(game.level_manager.background(), (0, 0))

        if self.player is not None and self.enemy is not None:
            # enemy behind, player in front (drawn second)
            draw_boxer(surface, self.enemy.x, config.GROUND_Y,
                       facing=-1, state=self.enemy.state,
                       anim_t=self.enemy.anim_t, scale=1.0,
                       trunks_color=self.enemy.trunks_color,
                       flash=False, hit_lean=0.0)
            draw_boxer(surface, self.player.x, config.GROUND_Y,
                       facing=1, state=self.player.state,
                       anim_t=self.player.anim_t, scale=self.player.scale,
                       trunks_color=C["trunks_player"],
                       flash=self.player.state == "hit",
                       hit_lean=1.0 if self.player.state == "hit" else 0.0)

            # debug: show hitboxes
            if game.debug_overlay and self.player.active_hitbox is not None:
                self._draw_hitbox(surface, self.player.active_hitbox, (120, 255, 120))
            if game.debug_overlay and self.enemy.active_hitbox is not None:
                self._draw_hitbox(surface, self.enemy.active_hitbox, (255, 120, 120))
            if game.debug_overlay:
                self._draw_hitbox(surface, self.player.body_hitbox, (120, 120, 255), 1)
                self._draw_hitbox(surface, self.enemy.body_hitbox, (255, 120, 255), 1)

            # impact text
            for impact in self.combat.impacts:
                alpha = max(0, int(255 * (impact.life / 0.7)))
                surf = game.fonts["large"].render(impact.text, True,
                                                  C["title_white"])
                surf.set_alpha(alpha)
                surface.blit(surf, surf.get_rect(center=(impact.x, impact.y)))

            # screen shake offset is applied at the very end (game shell)

            # countdown display while someone is down
            countdown = ""
            if self.player.is_knocked_down and not self.player.ko:
                countdown = str(max(0, config.KNOCKDOWN_MAX_COUNT - self.player.knockdown_count))
            elif self.enemy.is_knocked_down and not self.enemy.ko:
                countdown = str(max(0, config.KNOCKDOWN_MAX_COUNT - self.enemy.knockdown_count))            self.hud.draw(
                surface, self.player, self.enemy,
                distance_level=self.game.last_tracking.distance_level if self.game.last_tracking else "MEDIUM",
                camera_status=self.game.camera_status_text(),
                pose_present=self.game.last_tracking.pose_present if self.game.last_tracking else False,
                tracking_lost=self.game.tracking_lost_warning,
                countdown=countdown,
                fight_over=self.combat.fight_over,
                tracking=self.game.last_tracking,
            )
            self._draw_camera_preview(surface)

        # -- intro banner -------------------------------------------------
        if self.intro_timer > 0 and self.intro_banner:
            self._draw_intro(surface)

        # -- tutorial panel ----------------------------------------------
        if self.tutorial.active:
            self._draw_tutorial(surface)

    # ------------------------------------------------------------------
    def _draw_intro(self, surface: pygame.Surface) -> None:
        f = self.game.fonts
        banner = self.intro_banner
        center_x = config.BASE_WIDTH // 2

        round_text = f["medium"].render(
            f"ROUND {banner['round']}", True, C["warn_yellow"])
        name_text = f["big"].render(banner["opponent"].upper(), True, C["title_white"])
        loc_text = f["small"].render(
            f"{banner['location'].upper()}  -  {banner['subtitle'].upper()}",
            True, C["text_dim"])

        panel = pygame.Surface((560, 220), pygame.SRCALPHA)
        panel.fill((10, 9, 8, 210))
        surface.blit(panel, (center_x - 280, 220))
        pygame.draw.rect(surface, C["border"], (center_x - 280, 220, 560, 220), 1)

        surface.blit(round_text, round_text.get_rect(center=(center_x, 255)))
        surface.blit(name_text, name_text.get_rect(center=(center_x, 320)))
        surface.blit(loc_text, loc_text.get_rect(center=(center_x, 390)))

    def _draw_camera_preview(self, surface: pygame.Surface) -> None:
        """Live camera inset so players can verify pose alignment in-match."""
        game = self.game
        if game.settings["input_mode"] != "camera" or game.last_camera_frame is None:
            return
        frame = game.last_camera_frame
        if game.last_pose is not None and game.last_pose.present:
            frame = game.pose_tracker.draw_debug_frame(frame, game.last_pose)
        rgb = frame[:, :, ::-1]
        camera_surface = pygame.image.frombuffer(
            rgb.copy(), (rgb.shape[1], rgb.shape[0]), "RGB")
        preview_size = (256, 144)
        preview = pygame.transform.scale(camera_surface, preview_size)
        x, y = config.BASE_WIDTH - preview_size[0] - 18, 82
        panel = pygame.Rect(x - 4, y - 22, preview_size[0] + 8,
                            preview_size[1] + 26)
        pygame.draw.rect(surface, C["panel"], panel)
        pygame.draw.rect(surface, C["border"], panel, 1)
        label = game.fonts["tiny"].render("CAMERA PREVIEW", True, C["text"])
        surface.blit(label, (x, y - 18))
        surface.blit(preview, (x, y))

    def _draw_tutorial(self, surface: pygame.Surface) -> None:
        f = self.game.fonts
        x, y = 24, 84
        panel = pygame.Surface((360, 200), pygame.SRCALPHA)
        panel.fill((10, 9, 8, 200))
        surface.blit(panel, (x, y))
        pygame.draw.rect(surface, C["border"], (x, y, 360, 200), 1)
        title = f["small"].render("TUTORIAL", True, C["warn_yellow"])
        surface.blit(title, (x + 12, y + 8))
        yy = y + 34
        for check in self.tutorial._checks:
            color = C["ok_green"] if check["done"] else C["text_dim"]
            mark = "OK  " if check["done"] else "-  "
            line = f["tiny"].render(mark + check["text"], True, color)
            surface.blit(line, (x + 12, yy))
            yy += 26

    @staticmethod
    def _draw_hitbox(surface, hitbox, color, width: int = 2) -> None:
        pygame.draw.rect(surface, color,
                         (int(hitbox.x), int(hitbox.y),
                          int(hitbox.w), int(hitbox.h)), width)


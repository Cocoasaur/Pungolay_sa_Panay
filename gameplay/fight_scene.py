"""The FightScene: one boxing match between the player and an enemy.

Owns the two fighters, the enemy AI, combat resolution, HUD, intro banner,
tutorial panel and the fight-end transition. All camera work stays inside
the Game shell -- this scene only consumes TrackingData.
"""

from __future__ import annotations
from ui.fonts import cached_text

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
from gameplay.spacing import separate_fighters
from gameplay.tutorial import TutorialManager
from ui.hud import HUD, overlay_panel, compact_control
from ui.sprites import draw_boxer
from ui.camera_preview import preview_key, render_preview, label_guides

C = config.COLORS

FIGHT_OVER_DELAY = 1.6  # seconds the KO pose is shown before the screen
INTRO_BANNER_TIME = 2.8


class FightScene(Scene):
    name = "gameplay"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.hud = HUD(game.fonts)
        self._preview_key = None
        self._preview_surface = None
        self.preview_toggle_rect = pygame.Rect(20, 104, 96, 24)
        self.recenter_rect = pygame.Rect(116, 104, 96, 24)
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
        minimum = config.ARENA_MARGIN + self.player.body_w / 2
        position = (self.player.x - minimum) / (config.BASE_WIDTH - 2 * minimum)
        game.movement.recenter(position)
        game.keyboard.reset(position)
        self.enemy = Enemy(game.progression.opponent, x=config.BASE_WIDTH // 2 + 180)
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
        from ui.animation import prewarm_pair

        prewarm_pair(("player", 1), (self.game.progression.opponent_id, -1))

    def exit(self):
        if self.player is not None:
            self.player.ability_ready = False
        self.game.keyboard.reset()

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            key = pygame.key.name(event.key)
            if key == "f4":
                self._toggle_preview()
                return
            if key == "r":
                self.game.recenter_movement()
                return
            if key == "escape":
                if self.combat.fight_over:
                    return
                self.game.audio.play("menu_move")
                from ui.pause_menu import PauseMenu

                self.game.states.push(PauseMenu(self.game))

        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.game.settings["input_mode"] == "camera"
        ):
            if self.preview_toggle_rect.collidepoint(event.pos):
                self._toggle_preview()
            elif self.recenter_rect.collidepoint(event.pos):
                self.game.recenter_movement()

    def _toggle_preview(self):
        self.game.settings["camera_preview"] = not self.game.settings.get("camera_preview", True)
        self.game.apply_settings_changes()

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        game = self.game
        now = time.monotonic()
        tracking = game.get_current_tracking()
        self.player.is_charging = tracking.is_charging and not self.player.ability_ready
        self.player.charge_progress = 1 if self.player.ability_ready else tracking.charge_progress

        if tracking.charge_completed:
            self.player.ability_ready = True

        if self.intro_timer > 0:
            from ui.animation_cache import cache

            if not cache.pending:
                self.intro_timer -= dt
            return

        # fighters freeze during the hit-stop beat
        if self.combat.hitstop > 0:
            self.combat.update(dt, self.player, self.enemy)
            return

        # -- fighters ----------------------------------------------------
        previous_enemy_x = self.enemy.x
        previous_player_x = self.player.x
        self.player.update(dt, tracking, now, defer_motion=True)
        self.enemy.update(dt, now)
        if self.ai is not None and not self.combat.fight_over:
            previous_enemy_state = self.enemy.state
            self.ai.update(dt, self.player.state in ("punch_l", "punch_r"))
            if self.enemy.state != previous_enemy_state:
                self.enemy.action_t = 0.0

        separate_fighters(self.player, self.enemy, previous_player_x, previous_enemy_x)
        self.player.finalize_motion(dt, previous_player_x)
        enemy_dx = self.enemy.x - previous_enemy_x
        self.enemy.motion_direction = (
            (1 if enemy_dx > 0 else -1)
            if abs(enemy_dx) / max(0.001, dt) >= config.WALK_ENTER_SPEED
            else 0
        )
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
        self.player.ability_ready = False
        game = self.game
        if self.combat.winner == "player":
            from ui.screens import VictoryScreen

            result = VictoryScreen(
                game, enemy_name=self.enemy.name, is_final=game.progression.is_final_fight
            )
            game.progression.record_victory()
            game.save_current_progress()
            game.states.push(result)
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
            draw_boxer(
                surface,
                self.enemy.x,
                config.GROUND_Y,
                facing=-1,
                state=(
                    self.enemy.hit_pose[0]
                    if self.enemy.state == "hit"
                    else (
                        self.enemy.state
                        if self.enemy.state not in ("approach", "retreat")
                        or self.enemy.motion_direction
                        else "idle"
                    )
                ),
                anim_t=self.enemy.anim_t,
                scale=1.0,
                trunks_color=self.enemy.trunks_color,
                flash=self.enemy.state == "hit" and self.enemy.state_timer > 0.15,
                hit_lean=0.0,
                fighter_id=game.progression.opponent_id,
                action_time=(
                    self.enemy.hit_pose[1]
                    if self.enemy.state == "hit"
                    else (
                        self.enemy.anim_t
                        if self.enemy.state in ("idle", "approach", "retreat")
                        else self.enemy.action_t
                    )
                ),
                punch_side=self.enemy.attack_side,
                charged=self.enemy.style == "haymaker",
            )
            draw_boxer(
                surface,
                self.player.x,
                config.GROUND_Y,
                facing=1,
                state=(
                    self.player.hit_pose[0]
                    if self.player.state == "hit"
                    else (
                        "charging"
                        if self.player.is_charging and self.player.state == "idle"
                        else self.player.state
                    )
                ),
                anim_t=self.player.anim_t,
                scale=self.player.scale,
                trunks_color=C["trunks_player"],
                flash=self.player.state == "hit" and self.player.state_timer > 0.22,
                hit_lean=1.0 if self.player.state == "hit" else 0.0,
                fighter_id="player",
                action_time=(
                    self.player.hit_pose[1]
                    if self.player.state == "hit"
                    else (
                        self.player.animation_t
                        if self.player.state in ("idle", "walk")
                        else self.player.action_t
                    )
                ),
                charged=self.player.is_haymaker_punch,
                motion_direction=self.player.motion_direction,
                punch_side=(
                    game.last_tracking.charge_side
                    if self.player.is_charging and game.last_tracking
                    else self.player.punch_side
                ),
            )

            # debug: show hitboxes
            if game.debug_overlay and self.player.active_hitbox is not None:
                self._draw_hitbox(surface, self.player.active_hitbox, (120, 255, 120))
            if game.debug_overlay and self.enemy.active_hitbox is not None:
                self._draw_hitbox(surface, self.enemy.active_hitbox, (255, 120, 120))
            if game.debug_overlay:
                for hitbox in self.player.body_hitboxes:
                    self._draw_hitbox(surface, hitbox, (120, 120, 255), 1)
                for hitbox in self.enemy.body_hitboxes:
                    self._draw_hitbox(surface, hitbox, (255, 120, 255), 1)

            # impact text
            for impact in self.combat.impacts:
                alpha = max(0, int(255 * (impact.life / 0.7)))
                surf = cached_text(game.fonts["large"], impact.text, C["title_white"])
                surf.set_alpha(alpha)
                surface.blit(surf, surf.get_rect(center=(impact.x, impact.y)))

            # screen shake offset is applied at the very end (game shell)

            # countdown display while someone is down
            countdown = ""
            if self.player.is_knocked_down and not self.player.ko:
                countdown = str(max(0, config.KNOCKDOWN_MAX_COUNT - self.player.knockdown_count))
            elif self.enemy.is_knocked_down and not self.enemy.ko:
                countdown = str(max(0, config.KNOCKDOWN_MAX_COUNT - self.enemy.knockdown_count))
            self.hud.draw(
                surface,
                self.player,
                self.enemy,
                distance_level=(
                    self.game.last_tracking.distance_level if self.game.last_tracking else "MEDIUM"
                ),
                camera_status=self.game.camera_status_text(),
                pose_present=(
                    self.game.last_tracking.pose_present if self.game.last_tracking else False
                ),
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

        round_text = cached_text(
            f["medium"], f"STARTING IN {max(1, int(self.intro_timer + 0.999))}", C["warn_yellow"]
        )
        name_text = cached_text(f["big"], banner["opponent"].upper(), C["title_white"])
        loc_text = cached_text(
            f["small"],
            f"{banner['location'].upper()}  -  {banner['subtitle'].upper()}",
            C["title_white"],
        )

        panel = pygame.Surface((560, 220), pygame.SRCALPHA)
        panel.fill((10, 9, 8, 210))
        surface.blit(panel, (center_x - 280, 220))
        pygame.draw.rect(surface, C["border"], (center_x - 280, 220, 560, 220), 1)

        surface.blit(round_text, round_text.get_rect(center=(center_x, 255)))
        surface.blit(name_text, name_text.get_rect(center=(center_x, 320)))
        location_pill = pygame.Rect(
            center_x - loc_text.get_width() // 2 - 18, 371, loc_text.get_width() + 36, 38
        )
        pygame.draw.rect(surface, (28, 24, 20), location_pill, border_radius=8)
        pygame.draw.rect(surface, C["warm_glow"], location_pill, width=2, border_radius=8)
        surface.blit(loc_text, loc_text.get_rect(center=(center_x, 390)))

    def _draw_camera_preview(self, surface: pygame.Surface) -> None:
        """Live camera inset so players can verify pose alignment in-match."""
        game = self.game
        if game.settings["input_mode"] != "camera":
            return
        visible = game.settings.get("camera_preview", True)
        compact_control(
            surface, self.preview_toggle_rect, "HIDE / F4" if visible else "CAMERA / F4"
        )
        compact_control(surface, self.recenter_rect, "RECENTER R")
        if not visible:
            return
        frame_rect = pygame.Rect(20, 128, 192, 108)
        if game.last_camera_frame is None:
            overlay_panel(surface, frame_rect)
            label = cached_text(game.fonts["tiny"], "Waiting for camera…", C["text_dim"])
            surface.blit(label, label.get_rect(center=frame_rect.center))
            return
        key = preview_key(game)
        if key != self._preview_key:
            frame = render_preview(game, game.last_camera_frame, game.last_pose)
            rgb = frame[:, :, ::-1].copy()
            image = pygame.image.frombuffer(rgb, (rgb.shape[1], rgb.shape[0]), "RGB")
            self._preview_surface = pygame.transform.smoothscale(image, frame_rect.size)
            label_guides(self._preview_surface, game.fonts)
            self._preview_key = key
        surface.blit(self._preview_surface, frame_rect)
        pygame.draw.rect(surface, C["border"], frame_rect, 1)

    def _draw_tutorial(self, surface: pygame.Surface) -> None:
        """Show the next unfinished objective without covering the arena."""
        checks = self.tutorial._checks
        remaining = next((check for check in checks if not check["done"]), None)
        if remaining is None:
            return
        rect = pygame.Rect(448, 18, 384, 58)
        overlay_panel(surface, rect)
        done = sum(check["done"] for check in checks)
        self.hud._label(
            surface, f"PRACTICE / {done} OF {len(checks)}", (460, 26), 360, 12, C["warm_glow"], True
        )
        self.hud._label(surface, remaining["text"], (460, 47), 360, 15)

    @staticmethod
    def _draw_hitbox(surface, hitbox, color, width: int = 2) -> None:
        pygame.draw.rect(
            surface, color, (int(hitbox.x), int(hitbox.y), int(hitbox.w), int(hitbox.h)), width
        )

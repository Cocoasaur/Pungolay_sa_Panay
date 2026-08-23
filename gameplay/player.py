"""The player fighter.

Consumes TrackingData (from camera or keyboard) and exposes everything the
combat system needs: stats, states, hitboxes and the animation state for the
sprite renderer.

States: idle, walk, punch_l, punch_r, guard, hit, knockdown, ko
"""

from __future__ import annotations

from typing import Optional

import config
from core.tracking import TrackingData
from gameplay.hitbox import Hitbox

P = config.PLAYER


class Player:
    def __init__(self, x: float = config.BASE_WIDTH / 2) -> None:
        # --- stats (single source of truth: config.PLAYER) --------------
        self.max_hp = float(P["max_hp"])
        self.hp = self.max_hp
        self.max_stamina = float(P["max_stamina"])
        self.stamina = self.max_stamina
        self.punch_damage = float(P["punch_damage"])
        self.punch_cooldown = float(P["punch_cooldown"])
        self.move_speed = float(P["move_speed"])
        self.reach = float(P["reach"])
        self.guard_damage_reduction = float(P["guard_damage_reduction"])

        # --- motion -----------------------------------------------------
        self.x = x
        self.facing = 1                 # +1 = toward the enemy (right)
        self.scale = 1.0                # from distance estimation
        self.body_w = 54
        self.body_h = 132

        # --- state machine ----------------------------------------------
        self.state = "idle"
        self.state_timer = 0.0
        self.punch_side = "left"
        self.attack_id = 0
        self.active_hitbox: Optional[Hitbox] = None
        self.invuln_timer = 0.0         # seconds of remaining invulnerability
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.ko = False
        self.guarding = False
        self.anim_t = 0.0               # animation clock (idle bob, etc.)

        # input bookkeeping
        self._punch_cooldown = 0.0

    # ------------------------------------------------------------------
    @property
    def body_hitboxes(self) -> list[Hitbox]:
        w = self.body_w * self.scale
        h = self.body_h * self.scale
        
        # Split into Head and Torso
        head_h = h * 0.3
        torso_h = h * 0.7
        
        head = Hitbox(self.x - w / 2, config.GROUND_Y - h, w, head_h,
                      owner="player", body_part="HEAD")
        torso = Hitbox(self.x - w / 2, config.GROUND_Y - h + head_h, w, torso_h,
                       owner="player", body_part="TORSO")
        return [head, torso]

    @property
    def is_knocked_down(self) -> bool:
        return self.state in ("knockdown", "ko")

    # ------------------------------------------------------------------
    def update(self, dt: float, tracking: TrackingData, now: float) -> None:
        self.anim_t += dt
        self.scale = tracking.player_scale
        self.guarding = False
        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        self._punch_cooldown = max(0.0, self._punch_cooldown - dt)

        if self.is_knocked_down:
            self._update_knockdown(dt, tracking)
            return

        # -- movement (smoothed, clamped to the arena) ------------------
        if tracking.present:
            arena_min = config.ARENA_MARGIN + self.body_w * self.scale / 2
            arena_max = config.BASE_WIDTH - config.ARENA_MARGIN - self.body_w * self.scale / 2
            target_x = arena_min + tracking.horizontal_position * (arena_max - arena_min)
            k = 1.0 - (0.05 ** (dt * 60.0))   # residual jitter removal
            self.x += (target_x - self.x) * k
        half = self.body_w * self.scale / 2
        self.x = max(config.ARENA_MARGIN + half,
                     min(config.BASE_WIDTH - config.ARENA_MARGIN - half, self.x))

        # -- guard -------------------------------------------------------
        if tracking.guard and self.state in ("idle", "walk"):
            self.guarding = True
            self.state = "guard"

        # -- punches (edge-triggered from camera or keyboard) ------------
        punch_side = None
        is_haymaker = False
        if tracking.left_haymaker:
            punch_side = "left"
            is_haymaker = True
        elif tracking.right_haymaker:
            punch_side = "right"
            is_haymaker = True
        elif tracking.left_punch:
            punch_side = "left"
        elif tracking.right_punch:
            punch_side = "right"
            
        if punch_side is not None:
            self._start_punch(punch_side, now, is_haymaker)

        # -- stamina -----------------------------------------------------
        if self.guarding:
            self.stamina = max(0.0, self.stamina - P["guard_stamina_drain"] * dt)
        else:
            self.stamina = min(self.max_stamina,
                               self.stamina + P["stamina_regen"] * dt)

        # -- state timers ------------------------------------------------
        if self.state in ("punch_l", "punch_r"):
            self._update_punch(dt)
        elif self.state == "hit":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "idle"
        elif self.state == "guard":
            if not self.guarding:
                self.state = "idle"
        else:
            moving = tracking.present and abs(
                tracking.horizontal_position - 0.5) > 0.01
            self.state = "walk" if moving else "idle"

    # ------------------------------------------------------------------
    def _start_punch(self, side: str, now: float, is_haymaker: bool = False) -> None:
        self.is_haymaker_punch = is_haymaker
        if self._punch_cooldown > 0.0:
            return
        if self.state in ("punch_l", "punch_r", "hit") or self.is_knocked_down:
            return
        self._punch_cooldown = self.punch_cooldown
        self.punch_side = side
        self.state = "punch_l" if side == "left" else "punch_r"
        self.state_timer = P["punch_active_end"] + P["punch_recover"]
        self.active_hitbox = None

    def _update_punch(self, dt: float) -> None:
        self.state_timer -= dt
        elapsed = (P["punch_active_end"] + P["punch_recover"]) - self.state_timer
        if P["punch_active_start"] <= elapsed <= P["punch_active_end"]:
            if self.active_hitbox is None:
                # The box spans from just inside the body edge to the full
                # reach, so it lands on anyone in front within arm's length
                # (also when the fighters are standing very close).
                self.attack_id += 1
                reach = self.reach * self.scale
                hw = self.body_w * self.scale * 0.35 + reach
                hh = 26 * self.scale
                hand_y = config.GROUND_Y - self.body_h * self.scale * 0.62
                edge = self.x + self.facing * self.body_w * self.scale * 0.35
                self.active_hitbox = Hitbox(
                    min(edge, edge + self.facing * hw) - hw / 2,
                    hand_y - hh / 2, hw, hh,
                    owner="player", attack_id=self.attack_id,
                    damage=self.punch_damage, knockback=70)
        elif elapsed > P["punch_active_end"]:
            self.active_hitbox = None
        if self.state_timer <= 0:
            self.active_hitbox = None
            self.state = "idle"

    # ------------------------------------------------------------------
    def take_hit(self, damage: float, knockback: float, from_direction: int) -> bool:
        """Apply damage. Returns False when the hit is absorbed (i-frames)."""
        if self.is_knocked_down or self.invuln_timer > 0.0:
            return False
        if self.guarding:
            damage *= (1.0 - self.guard_damage_reduction)
            self.stamina = max(0.0, self.stamina - P["block_stamina_cost"])
        self.hp = max(0.0, self.hp - damage)
        self.state = "hit"
        self.state_timer = 0.3
        self.active_hitbox = None
        self.invuln_timer = P["hit_invuln"]
        return True

    def force_knockdown(self) -> None:
        self.state = "knockdown"
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.active_hitbox = None

    def _update_knockdown(self, dt: float, tracking: TrackingData) -> None:
        if self.state == "ko":
            return
        self.knockdown_time += dt
        ticks = int(self.knockdown_time / config.KNOCKDOWN_COUNT_INTERVAL)
        if ticks > self.knockdown_count:
            self.knockdown_count = min(config.KNOCKDOWN_MAX_COUNT, ticks)
            if self.knockdown_count >= config.KNOCKDOWN_MAX_COUNT:
                self.state = "ko"
                return
        if tracking.hands_up:
            self.get_up()

    def get_up(self) -> None:
        if self.state == "ko":
            return
        self.state = "idle"
        self.hp = max(self.hp, self.max_hp * P["knockdown_recover_hp"])
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.invuln_timer = 1.2          # brief protection after getting up

    def reset(self, x: Optional[float] = None) -> None:
        self.__init__(x if x is not None else self.x)

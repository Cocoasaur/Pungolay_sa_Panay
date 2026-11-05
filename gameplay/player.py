"""The player fighter.

Consumes TrackingData (from camera or keyboard) and exposes everything the
combat system needs: stats, states, hitboxes and the animation state for the
sprite renderer.

States: idle, walk, punch_l, punch_r, guard, hit, knockdown, ko
"""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class AttackSnapshot:
    side: str
    attack_type: str
    damage: float


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
        self.reach = float(P["reach"]) * config.FIGHTER_SIZE
        self.guard_damage_reduction = float(P["guard_damage_reduction"])

        # --- motion -----------------------------------------------------
        self.x = x
        self.facing = 1  # +1 = toward the enemy (right)
        self.scale = 1.0  # from distance estimation
        self.body_w = config.FIGHTER_BODY_WIDTH
        self.body_h = config.FIGHTER_BODY_HEIGHT

        # --- state machine ----------------------------------------------
        self.state = "idle"
        self.state_timer = 0.0
        self.punch_side = "left"
        self.attack_id = 0
        self.active_hitbox: Optional[Hitbox] = None
        self.invuln_timer = 0.0  # seconds of remaining invulnerability
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.ko = False
        self.guarding = False
        self.ability_ready = False
        self.accepted_attack = None
        self.is_haymaker_punch = False
        self.charge_progress = 0.0
        self.is_charging = False
        self.motion_direction = 0
        self._velocity = 0.0
        self._walk_still = 0.0
        self.hit_pose = ("idle", 0.0)
        self.animation_t = 0.0
        self.action_t = 0.0
        self.anim_t = 0.0  # animation clock (idle bob, etc.)

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

        head = Hitbox(
            self.x - w / 2, config.GROUND_Y - h, w, head_h, owner="player", body_part="HEAD"
        )
        torso = Hitbox(
            self.x - w / 2,
            config.GROUND_Y - h + head_h,
            w,
            torso_h,
            owner="player",
            body_part="TORSO",
        )
        return [head, torso]

    @property
    def is_knocked_down(self) -> bool:
        return self.state in ("knockdown", "ko")

    @property
    def is_incapacitated(self):
        return self.state in ("knockdown", "getup", "ko")

    # ------------------------------------------------------------------
    def update(self, dt: float, tracking: TrackingData, now: float, defer_motion=False) -> None:
        self.anim_t += dt
        self.animation_t += dt
        self.action_t += dt
        if tracking.charge_completed:
            self.ability_ready = True
        self.is_charging = tracking.is_charging and not self.ability_ready
        self.charge_progress = 1.0 if self.ability_ready else tracking.charge_progress
        previous_x = self.x
        previous_state = self.state
        self.scale = 1.0
        self.guarding = False
        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        self._punch_cooldown = max(0.0, self._punch_cooldown - dt)

        if self.state == "getup":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "idle"
                self.action_t = 0
                self.invuln_timer = 1.2
            return
        if self.is_knocked_down:
            self._update_knockdown(dt, tracking)
            return

        # -- movement: bounded speed and acceleration, not render-rate lerp --
        half = self.body_w / 2
        arena_min = config.ARENA_MARGIN + half
        arena_max = config.BASE_WIDTH - config.ARENA_MARGIN - half
        if tracking.present and tracking.movement_valid:
            target_x = arena_min + tracking.horizontal_position * (arena_max - arena_min)
            error = target_x - self.x
            desired = (
                max(-self.move_speed, min(self.move_speed, error / 0.06)) if abs(error) > 0.5 else 0
            )
            acceleration = self.move_speed / config.MOVEMENT_ACCEL_TIME
            self._velocity += max(
                -acceleration * dt, min(acceleration * dt, desired - self._velocity)
            )
            step = self._velocity * dt
            if step * error > 0 and abs(step) > abs(error):
                step = error
                self._velocity = 0
            self.x += step
        else:
            self._velocity = 0
        self.x = max(arena_min, min(arena_max, self.x))

        # -- guard -------------------------------------------------------
        if tracking.guard and self.state in ("idle", "walk", "guard"):
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
            self.stamina = min(self.max_stamina, self.stamina + P["stamina_regen"] * dt)

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
        elif not defer_motion:
            self.finalize_motion(dt, previous_x)

        if self.state != previous_state:
            self.action_t = 0.0
        if self.state in ("punch_l", "punch_r"):
            self.action_t = P["punch_active_end"] + P["punch_recover"] - self.state_timer

    # ------------------------------------------------------------------
    def finalize_motion(self, dt, previous_x):
        if self.state not in ("idle", "walk"):
            return
        dx = self.x - previous_x
        speed = abs(dx) / max(dt, 0.001)
        if speed >= config.WALK_ENTER_SPEED:
            self.state = "walk"
            self._walk_still = 0
        elif speed <= config.WALK_EXIT_SPEED:
            self._walk_still += dt
            if self._walk_still >= config.WALK_STOP_TIME:
                self.state = "idle"
        self.motion_direction = (
            (1 if dx > 0 else -1) if self.state == "walk" and abs(dx) > 0.01 else 0
        )

    def _start_punch(self, side: str, now: float, is_haymaker: bool = False) -> bool:
        if self._punch_cooldown > 0.0:
            return False
        if self.state in ("punch_l", "punch_r", "hit") or self.is_incapacitated:
            return False
        self.is_haymaker_punch = self.ability_ready
        self.accepted_attack = AttackSnapshot(
            side,
            "HAYMAKER" if self.is_haymaker_punch else "NORMAL",
            self.punch_damage
            * (config.HAYMAKER_DAMAGE_MULTIPLIER if self.is_haymaker_punch else 1.0),
        )
        self.ability_ready = False
        self.guarding = False
        self.action_t = 0.0
        self._punch_cooldown = self.punch_cooldown
        self.punch_side = side
        self.state = "punch_l" if side == "left" else "punch_r"
        self.state_timer = P["punch_active_end"] + P["punch_recover"]
        self.active_hitbox = None
        return True

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
                hh = 26 * config.FIGHTER_SIZE * self.scale
                hand_y = config.GROUND_Y - self.body_h * self.scale * 0.62
                edge = self.x + self.facing * self.body_w * self.scale * 0.35
                self.active_hitbox = Hitbox(
                    min(edge, edge + self.facing * hw) - hw / 2,
                    hand_y - hh / 2,
                    hw,
                    hh,
                    owner="player",
                    attack_id=self.attack_id,
                    damage=self.accepted_attack.damage,
                    knockback=70,
                    attack_type=self.accepted_attack.attack_type,
                )
        elif elapsed > P["punch_active_end"]:
            self.active_hitbox = None
        if self.state_timer <= 0:
            self.active_hitbox = None
            self.state = "idle"

    # ------------------------------------------------------------------
    def take_hit(self, damage: float, knockback: float, from_direction: int) -> bool:
        """Apply damage. Returns False when the hit is absorbed (i-frames)."""
        if self.is_incapacitated or self.invuln_timer > 0.0:
            return False
        if self.guarding:
            damage *= 1.0 - self.guard_damage_reduction
            self.stamina = max(0.0, self.stamina - P["block_stamina_cost"])
        self.hit_pose = (
            self.state if self.state != "hit" else self.hit_pose[0],
            (
                (
                    self.anim_t
                    if self.state in ("idle", "walk", "approach", "retreat")
                    else self.action_t
                )
                if self.state != "hit"
                else self.hit_pose[1]
            ),
        )
        self.hp = max(0.0, self.hp - damage)
        self.state = "hit"
        self.state_timer = 0.3
        self.active_hitbox = None
        self.invuln_timer = P["hit_invuln"]
        return True

    def force_knockdown(self) -> None:
        self.state = "knockdown"
        self.action_t = 0.0
        self._velocity = 0.0
        self.guarding = False
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
        if tracking.hands_up and self.knockdown_time >= config.KNOCKDOWN_FALL_TIME:
            self.get_up()

    def get_up(self) -> None:
        if self.state == "ko":
            return
        self.state = "getup"
        self.state_timer = config.GETUP_TIME
        self.action_t = 0.0
        self.hp = max(self.hp, self.max_hp * P["knockdown_recover_hp"])
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.invuln_timer = config.GETUP_TIME + 1.2

    def reset(self, x: Optional[float] = None) -> None:
        self.__init__(x if x is not None else self.x)

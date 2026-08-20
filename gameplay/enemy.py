"""Enemy fighter with a simple finite-state machine.

States: idle, approach, windup, attack, recover, defend, retreat, hit,
knockdown, ko

Behaviour parameters come entirely from config.ENEMIES (data-driven), and the
state transitions are decided by gameplay/ai.py.
"""

from __future__ import annotations

import random
from typing import Optional

import config
from gameplay.hitbox import Hitbox


class Enemy:
    def __init__(self, archetype: dict, x: float) -> None:
        # --- stats from the archetype table -----------------------------
        self.name = archetype["name"]
        self.title = archetype.get("title", "")
        self.max_hp = float(archetype["hp"])
        self.hp = self.max_hp
        self.damage = float(archetype["damage"])
        self.speed = float(archetype["speed"])
        self.reach = float(archetype["reach"])
        self.preferred_distance = float(archetype["preferred_distance"])
        self.aggression = float(archetype["aggression"])
        self.guard_chance = float(archetype["guard_chance"])
        self.retreat_chance = float(archetype["retreat_chance"])
        self.attack_delay = float(archetype["attack_delay"])
        self.recover_time = float(archetype["recover_time"])
        self.reaction_time = float(archetype["reaction_time"])
        self.stagger_resist = float(archetype["stagger_resist"])
        self.style = archetype.get("style", "generic")
        self.trunks_color = archetype.get("trunks", (48, 22, 26))

        # --- motion & state ---------------------------------------------
        self.x = x
        self.facing = -1                 # toward the player (left)
        self.scale = 1.0
        self.body_w = 54
        self.body_h = 132

        self.state = "idle"
        self.state_timer = 0.0
        self.decision_timer = 0.0
        self.attack_id = 0
        self.active_hitbox: Optional[Hitbox] = None
        self.invuln_timer = 0.0
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.knockdowns_total = 0        # get-ups allowed per fight: 2
        self.ko = False
        self.guarding = False
        self.anim_t = 0.0

    # ------------------------------------------------------------------
    @property
    def body_hitbox(self) -> Hitbox:
        w = self.body_w * self.scale
        h = self.body_h * self.scale
        return Hitbox(self.x - w / 2, config.GROUND_Y - h, w, h,
                      owner="enemy")

    @property
    def is_knocked_down(self) -> bool:
        return self.state in ("knockdown", "ko")

    @property
    def is_attacking(self) -> bool:
        return self.state in ("windup", "attack")

    # ------------------------------------------------------------------
    def update(self, dt: float, now: float) -> None:
        self.anim_t += dt
        self.invuln_timer = max(0.0, self.invuln_timer - dt)

        if self.is_knocked_down:
            self._update_knockdown(dt)
            return

        if self.state == "idle":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "approach"
        elif self.state == "approach":
            pass  # movement applied by ai.apply_movement
        elif self.state == "windup":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "attack"
                self.attack_id += 1
                self._spawn_attack_hitbox()
        elif self.state == "attack":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.active_hitbox = None
                self.state = "recover"
                self.state_timer = self.recover_time
        elif self.state == "recover":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "idle"
        elif self.state == "defend":
            self.guarding = True
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.guarding = False
                self.state = "idle"
        elif self.state == "retreat":
            pass  # movement applied by ai.apply_movement
        elif self.state == "hit":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "idle"

    def _spawn_attack_hitbox(self) -> None:
        hw = self.body_w * self.scale * 0.35 + self.reach * self.scale
        hh = 30 * self.scale
        hand_y = config.GROUND_Y - self.body_h * self.scale * 0.62
        edge = self.x + self.facing * self.body_w * self.scale * 0.35
        self.active_hitbox = Hitbox(
            min(edge, edge + self.facing * hw) - hw / 2,
            hand_y - hh / 2, hw, hh,
            owner="enemy", attack_id=self.attack_id,
            damage=self.damage, knockback=80)

    # ------------------------------------------------------------------
    def take_hit(self, damage: float, knockback: float, from_direction: int) -> bool:
        if self.is_knocked_down or self.invuln_timer > 0.0:
            return False
        if self.guarding:
            damage *= 0.55              # enemies block less effectively
        self.hp = max(0.0, self.hp - damage)
        # stagger resistance: heavy fighters sometimes keep swinging
        if not (self.state in ("windup", "attack") and
                random.random() < self.stagger_resist):
            self.state = "hit"
            self.state_timer = max(0.15, 0.3 - self.stagger_resist * 0.3)
            self.guarding = False
            self.active_hitbox = None
        self.invuln_timer = 0.25
        return True

    def force_knockdown(self) -> None:
        self.state = "knockdown"
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.knockdowns_total += 1
        self.active_hitbox = None

    def _update_knockdown(self, dt: float) -> None:
        if self.state == "ko":
            return
        self.knockdown_time += dt
        ticks = int(self.knockdown_time / config.KNOCKDOWN_COUNT_INTERVAL)
        if ticks > self.knockdown_count:
            self.knockdown_count = min(config.KNOCKDOWN_MAX_COUNT, ticks)
            if self.knockdown_count >= config.KNOCKDOWN_MAX_COUNT:
                self.state = "ko"
                return
            # AI get-up: rises from count 3 onward (three-knockdown rule:
            # the third knockdown is final), heavier fighters rise later.
            if self.knockdowns_total < 3:
                getup_chance = 0.55 - self.stagger_resist * 0.5
                if self.knockdown_count >= 3 and random.random() < getup_chance:
                    self.state = "idle"
                    self.hp = max(self.hp, self.max_hp * 0.35)
                    self.knockdown_count = 0
                    self.knockdown_time = 0.0
                    self.invuln_timer = 1.0

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.hp = self.max_hp
        self.state = "idle"
        self.ko = False
        self.knockdown_count = 0
        self.knockdown_time = 0.0
        self.knockdowns_total = 0
        self.active_hitbox = None
        self.guarding = False
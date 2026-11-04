"""Enemy decision-making.

Every `reaction_time` seconds the AI re-evaluates the fight and picks a goal
state (approach / attack / defend / retreat). Movement toward that goal is
applied continuously. All probabilities come from the archetype data, so the
seven opponents behave differently with zero hardcoded per-fight logic.
"""

from __future__ import annotations

import random
from typing import Optional

import config
from gameplay.enemy import Enemy
from gameplay.player import Player


class EnemyAI:
    def __init__(self, enemy: Enemy, player: Player) -> None:
        self.enemy = enemy
        self.player = player

    # ------------------------------------------------------------------
    def update(self, dt: float, player_punching: bool) -> None:
        enemy = self.enemy
        if enemy.is_knocked_down or enemy.state in ("windup", "attack",
                                                    "recover", "hit", "defend"):
            return  # in-progress actions finish on their own

        enemy.decision_timer -= dt
        if enemy.decision_timer > 0:
            self._apply_movement(dt)
            return

        enemy.decision_timer = enemy.reaction_time
        dist = abs(enemy.x - self.player.x)
        attack_range = (enemy.reach + enemy.body_w) * enemy.scale * 0.9

        # --- player just threw a punch -> react defensively -------------
        if player_punching and enemy.state != "defend":
            if random.random() < enemy.guard_chance:
                enemy.state = "defend"
                enemy.state_timer = random.uniform(0.5, 1.1)
                self._apply_movement(dt)
                return
            if random.random() < enemy.retreat_chance:
                enemy.state = "retreat"
                enemy.state_timer = random.uniform(0.4, 0.8)

        # --- close enough -> attack -------------------------------------
        if dist <= attack_range and random.random() < enemy.aggression:
            enemy.attack_side = "left" if (enemy.attack_id+1) % 2 == 0 else "right"
            enemy.state = "windup"
            enemy.state_timer = enemy.attack_delay
            return

        # --- too far -> close in ----------------------------------------
        if dist > enemy.preferred_distance * 1.25:
            enemy.state = "approach"
        # --- too close -> occasionally step back ------------------------
        elif dist < enemy.preferred_distance * 0.55:
            if random.random() < enemy.retreat_chance:
                enemy.state = "retreat"
                enemy.state_timer = random.uniform(0.3, 0.6)
            else:
                enemy.state = "approach"
        else:
            enemy.state = "idle"
            enemy.state_timer = random.uniform(0.3, 0.8)

        self._apply_movement(dt)

    # ------------------------------------------------------------------
    def _apply_movement(self, dt: float) -> None:
        enemy = self.enemy
        player = self.player
        before_x = enemy.x

        if enemy.state == "approach":
            direction = 1 if player.x > enemy.x else -1
            enemy.x += direction * enemy.speed * 60 * dt
        elif enemy.state == "retreat":
            direction = -1 if player.x > enemy.x else 1
            enemy.x += direction * enemy.speed * 50 * dt

        half = enemy.body_w * enemy.scale / 2
        enemy.x = max(config.ARENA_MARGIN + half,
                      min(config.BASE_WIDTH - config.ARENA_MARGIN - half, enemy.x))
        dx = enemy.x - before_x
        enemy.motion_direction = (1 if dx>0 else -1) if abs(dx)>0.05 else 0
        if enemy.state in ("approach", "retreat") and enemy.motion_direction == 0:
            enemy.state = "idle"

    # ------------------------------------------------------------------
    def start_attack(self) -> bool:
        """Force an attack (used by the tutorial)."""
        enemy = self.enemy
        if enemy.is_knocked_down or enemy.state in ("windup", "attack", "hit"):
            return False
        enemy.attack_side = "left" if (enemy.attack_id+1) % 2 == 0 else "right"
        enemy.state = "windup"
        enemy.state_timer = enemy.attack_delay
        return True
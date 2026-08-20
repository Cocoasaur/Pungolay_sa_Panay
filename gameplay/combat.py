"""Combat resolution: hit detection, damage, reactions, knockdowns.

Keeps a per-attack ledger so a single punch can only ever damage its target
once, applies knockback, hit-stop, screen shake and impact text, and emits
events the audio system listens to.
"""

from __future__ import annotations

import random
from typing import List

import config
from core.events import EventBus
from gameplay.enemy import Enemy
from gameplay.hitbox import Hitbox
from gameplay.player import Player

IMPACT_WORDS = ["POW!", "TUK!", "BAG!", "THWAK!", "YOW!"]


class ImpactText:
    def __init__(self, x: float, y: float, text: str) -> None:
        self.x, self.y = x, y
        self.text = text
        self.life = 0.7

    def update(self, dt: float) -> None:
        self.life -= dt
        self.y -= 40 * dt

    @property
    def alive(self) -> bool:
        return self.life > 0


class CombatManager:
    def __init__(self, events: EventBus) -> None:
        self.events = events
        self._applied: set = set()       # (owner, attack_id) already resolved
        self.hitstop = 0.0
        self.shake = 0.0
        self.impacts: List[ImpactText] = []
        self.knockdown_fighter = None    # "player" | "enemy" | None
        self.fight_over = False
        self.winner = None

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._applied.clear()
        self.hitstop = 0.0
        self.shake = 0.0
        self.impacts.clear()
        self.knockdown_fighter = None
        self.fight_over = False
        self.winner = None

    def resolve(self, player: Player, enemy: Enemy, dt: float) -> None:
        """Check every active attack hitbox against the opposing body."""
        if self.fight_over or self.hitstop > 0:
            return
        if player.active_hitbox is not None:
            self._try_attack(player.active_hitbox, player, enemy,
                             target_is_player=False)
        if enemy.active_hitbox is not None:
            self._try_attack(enemy.active_hitbox, enemy, player,
                             target_is_player=True)

    def _try_attack(self, hitbox: Hitbox, attacker, target,
                    target_is_player: bool) -> None:
        key = (hitbox.owner, hitbox.attack_id)
        if key in self._applied:
            return
        if not hitbox.collides(target.body_hitbox):
            return
        self._applied.add(key)

        guarded = target.guarding
        landed = target.take_hit(hitbox.damage, hitbox.knockback,
                                 attacker.facing)
        if not landed:
            return

        # knockback pushes the target away from the attacker
        push = hitbox.knockback * (0.4 if guarded else 1.0)
        target.x += attacker.facing * push
        target.x = max(config.ARENA_MARGIN + target.body_w / 2,
                       min(config.BASE_WIDTH - config.ARENA_MARGIN -
                           target.body_w / 2, target.x))

        # ---- feedback ---------------------------------------------------
        self.hitstop = config.HITSTOP_TIME
        self.shake = (config.SCREEN_SHAKE_BIG if target.hp <= 0
                      else config.SCREEN_SHAKE_HIT)
        cx, cy = hitbox.center()
        self.impacts.append(ImpactText(cx, cy, random.choice(IMPACT_WORDS)))
        self.events.emit("block" if guarded else "hit", guard=guarded)

        # ---- knockdown --------------------------------------------------
        if target.hp <= 0 and not target.is_knocked_down:
            target.force_knockdown()
            self.knockdown_fighter = "player" if target_is_player else "enemy"
            self.shake = max(self.shake, config.SCREEN_SHAKE_BIG)
            self.events.emit("knockdown", fighter=self.knockdown_fighter)

    # ------------------------------------------------------------------
    def update(self, dt: float, player: Player, enemy: Enemy) -> None:
        self.hitstop = max(0.0, self.hitstop - dt)
        self.shake = max(0.0, self.shake - 30 * dt)
        for impact in self.impacts:
            impact.update(dt)
        self.impacts = [i for i in self.impacts if i.alive]

        if not self.fight_over:
            if player.state == "ko":
                self.fight_over = True
                self.winner = "enemy"
                self.events.emit("defeat")
            elif enemy.state == "ko":
                self.fight_over = True
                self.winner = "player"
                self.events.emit("victory")
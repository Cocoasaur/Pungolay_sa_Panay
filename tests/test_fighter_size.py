"""Combat checks for the larger fighter geometry."""

import unittest

import config
from core.events import EventBus
from gameplay.combat import CombatManager
from gameplay.enemy import Enemy
from gameplay.hitbox import Hitbox
from gameplay.player import Player


class FighterSizeTests(unittest.TestCase):
    def test_both_fighters_can_land_punches_at_larger_spacing(self):
        for attacker in ("player", "enemy"):
            with self.subTest(attacker=attacker):
                player = Player(x=500)
                enemy = Enemy(config.ENEMIES["jessie"], x=650)
                combat = CombatManager(EventBus())
                if attacker == "player":
                    player._start_punch("right", 0)
                    player._update_punch(0.1)
                    target = enemy
                else:
                    enemy._spawn_attack_hitbox()
                    target = player
                before = target.hp
                combat.resolve(player, enemy, 1 / 60)
                self.assertLess(target.hp, before)

    def test_knockback_keeps_scaled_body_inside_arena(self):
        player = Player(x=1000)
        enemy = Enemy(config.ENEMIES["jessie"], x=1180)
        enemy.scale = 1.25
        torso = enemy.body_hitboxes[1]
        player.active_hitbox = Hitbox(
            torso.x, torso.y, torso.w, torso.h, owner="player",
            attack_id=1, damage=8, knockback=500)
        CombatManager(EventBus()).resolve(player, enemy, 1 / 60)
        body_right = enemy.x + enemy.body_w * enemy.scale / 2
        self.assertLessEqual(body_right, config.BASE_WIDTH - config.ARENA_MARGIN)


if __name__ == "__main__":
    unittest.main()

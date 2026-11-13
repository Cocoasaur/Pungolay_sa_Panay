"""Keep fighter bodies separated and inside the arena without crossing."""

import config


def separate_fighters(player, enemy, previous_player_x=None, previous_enemy_x=None):
    left_min = config.ARENA_MARGIN + player.body_w / 2
    right_max = config.BASE_WIDTH - config.ARENA_MARGIN - enemy.body_w / 2
    gap = (player.body_w + enemy.body_w) / 2 + config.FIGHTER_SEPARATION
    px = max(left_min, min(right_max - gap, player.x))
    ex = max(left_min + gap, min(right_max, enemy.x))
    if ex - px < gap and previous_player_x is not None and previous_enemy_x is not None:
        # Clip each fighter's closing motion instead of shoving a stationary
        # opponent. Knockback is handled separately by combat.
        player_closing = max(0, px - previous_player_x)
        enemy_closing = max(0, previous_enemy_x - ex)
        closing = player_closing + enemy_closing
        if closing > 0:
            overlap = gap - (ex - px)
            px -= overlap * player_closing / closing
            ex += overlap * enemy_closing / closing
    if ex - px < gap - 1e-6:
        midpoint = (px + ex) / 2
        px = midpoint - gap / 2
        ex = midpoint + gap / 2
        if px < left_min:
            ex += left_min - px
            px = left_min
        if ex > right_max:
            px -= ex - right_max
            ex = right_max
    for fighter, new_x in ((player, px), (enemy, ex)):
        if fighter.active_hitbox is not None:
            fighter.active_hitbox.x += new_x - fighter.x
        fighter.x = new_x

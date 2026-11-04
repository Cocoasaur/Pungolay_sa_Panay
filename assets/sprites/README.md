# Fighter sprites

Replace the included transparent PNG templates with your artwork. There is a
default template for the player and one for each of the seven opponents:

- `player.png` - the player's default pose
- `jessie.png`
- `jevidiah.png`
- `johnwilt.png`
- `jereme.png`
- `daniel.png`
- `blacc_twenti_too.png`
- `caloy.png`

Visible sprites are resized to 240 pixels tall at neutral camera distance,
centered horizontally at the fighter's position, and aligned by their bottom
edge with the fighter's feet. Transparent padding is trimmed when loading,
so it cannot make a character look smaller or float above the ground.
`config.FIGHTER_SIZE` controls the shared size multiplier for rendering,
body hitboxes, punch reach, and enemy spacing. Camera distance still scales
the player relative to this size. The image should face right; the game
flips it for fighters facing left.

To animate actions, add state-specific images named with the fighter ID and
state, for example `player_punch_l.png`, `jessie_guard.png`, or
`caloy_knockdown.png`. A matching state image takes precedence over that
fighter's default image. States without a matching image use that fighter's
default image. `enemy.png` and `enemy_<state>.png` can be used as shared
fallbacks for opponents. If no image applies, the original procedurally drawn
fighter is used.

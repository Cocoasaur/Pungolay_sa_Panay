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


## Generated action animation

`animations.json` describes six clips for each of the eight original fighters:
left/right punches (3 frames each), guard (2), walking (4), and charged
left/right punches (3 each). There are 48 transparent sheets and 144 used frames.
`animations/generation.json` records the built-in imagegen prompts and mode.
Each generation used that fighter's original PNG as its identity reference.

Each square sheet has a 2×2 row-major grid. The manifest uses actual output
sizes, a uniform cell inset to exclude seams, frame rectangles, normalized sole
pivots, durations, and one shared body-height reference per fighter. Unused
cells are never rendered. Frames are not independently cropped or resized:
all eighteen frames share that fighter's scale, and sole pivots meet GROUND_Y.
The reference corresponds to the existing 240-pixel neutral fighter height.

Player punch windup, extension, and recovery follow config.PLAYER hitbox timing.
Enemy states explicitly select windup/extension/recovery, with a 160 ms active
attack window. Guard raises then holds; walking loops only while actually
moving, and backward steps preserve facing. Charged punches select their own
left/right clips. Missing sheets/clips fall back to legacy state PNGs, then the
fighter PNG, then the procedural renderer.

The authored sheets remain unchanged from imagegen output. The cell inset and
manifest frame bounds exclude occasional unused-cell artifacts. QA checked all
144 used cells for transparency, edge contact, soles, anatomy, and identity.

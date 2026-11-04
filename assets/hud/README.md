# Editable HUD overlay

The starter design is `template.png` (1280 x 720 with transparency). To use
and edit it, copy it to this folder as `hud.png`, then modify `hud.png` in an
image editor. The game loads that file as a transparent overlay behind the
live HUD. If `hud.png` is absent, the regular HUD is unchanged.

Keep the canvas at 1280 x 720. Transparent pixels show the game beneath the
overlay. The game draws health and stamina bars, fighter names, distance,
camera status, and countdown text after the overlay, so those live indicators
remain visible. The current bar fills and text colors are still drawn by the
game; use the PNG to customize the panels, borders, and decoration around
them.

The top panel contains the health bars, fighter names, and opponent title.
The bottom panel contains camera status and distance. Keep important art away
from the center of the screen and preserve transparency where live text and
indicators appear.

# Editable main menu background and overlay

`templates\menu_background.png` is a 1280 x 720 PNG template of the current
procedural gym background. Copy it to this folder as `menu_background.png`
and edit that file to replace the main menu's background. The game scales it
to 1280 x 720 if needed. If `menu_background.png` is absent, the procedural
background is used.

This is a full background, not a transparent overlay. The game draws the
live title, menu options, boxers, and controls on top of it. Keep those areas
clear enough for the interface to remain readable.

The separate `menu.png` file is the legacy transparent decorative overlay.
It is only drawn when `menu_background.png` is absent; the custom background
takes precedence so an old overlay cannot hide it.

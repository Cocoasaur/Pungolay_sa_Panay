# Location background images

The game has seven editable location backgrounds. PNG files placed directly
in this folder override the corresponding procedural backdrop:

- `black22.png`
- `citi_hardware.png`
- `jaro_plaza.png`
- `pavia_plaza.png`
- `jollibee_sta_barbara.png`
- `iloilo_airport.png`
- `caloy_house.png`

Starter PNGs are in `templates`. Copy a template here using the matching name
to enable it, then edit it with an image editor. For example, copy
`templates\black22.png` to `black22.png`. The game uses a custom background
as a transparent overlay on top of its existing arena, so transparent areas
keep the procedural art visible. Opaque areas replace it. Images of any size
are resized to the game's 1280 x 720 canvas.

The ring floor begins at y=520, ropes run across y=352, 388, and 424, and the
fighters stand with their feet at y=568. Keep important background details
above or behind these arena elements so the ring and fighters remain visible.
If a location PNG is absent, the original procedural backdrop is used.

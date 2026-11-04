# Editable screen overlays

Each screen can have a separate transparent PNG overlay. Copy a template from
`templates` into this folder with the same filename to enable it, then edit
that copy. For example, copy `templates\victory.png` to `victory.png`.

Templates are 1280 x 720. Transparent pixels show the screen beneath.
Overlays are drawn behind dynamic text, menu options, selection highlights,
and camera previews so the interface remains usable. If an overlay file is
missing, that screen's normal appearance is unchanged.

Available templates:

- `victory.png`
- `defeat.png`
- `camera_error.png`
- `calibration.png`
- `load_game.png`
- `level_select.png`
- `camera_debug.png`
- `settings.png`

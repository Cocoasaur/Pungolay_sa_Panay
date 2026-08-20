# PUNGOLAY SA PANAY

A 2D boxing game played with your **body** in front of a webcam. Move left and
right to step, punch the air to throw punches, raise both hands to your face
to guard, and raise both arms to get up from a knockdown. Seven opponents
await you across seven Panay locations, from the Black 22 gym in Iloilo City
to the Iloilo International Airport.

Built with Python, Pygame Community Edition, OpenCV and MediaPipe — no fake
inputs, no pre-recorded motion: every frame of the game reacts to real pose
estimation from your camera.

## Requirements

- Linux (developed and tested on Python 3.11+ / 3.14); Windows support planned
- A webcam (any UVC/V4L2 camera works)
- ~60 MB of disk space for models and sounds

## Setup (Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/setup_assets.py     # downloads pose models + bundles fonts
python main.py
```

`scripts/setup.sh` runs all of the above in one go. Without the models the
game still runs — in keyboard mode.

## How to play

| Action        | Camera gesture                              | Keyboard      |
|---------------|---------------------------------------------|---------------|
| Move          | Step toward the camera to advance right, step back to retreat left, step sideways to reposition | A / D, ← / → |
| Left punch    | Punch the air with your left hand           | J             |
| Right punch   | Punch the air with your right hand          | K             |
| Guard         | Both hands up near your face (hold)         | Hold Space    |
| Get up        | Both hands raised high (or Space)           | Space         |

Controls and input mode are configurable in **SETTINGS** (also reachable with
F1 in a fight). Press **F3** for a live debug overlay and **F11** for
fullscreen. If camera movement ever feels reversed, toggle **MIRROR INPUT** in
SETTINGS.

## Fight flow

- Each fight is three-knockdown: go down three times and you're out.
- Your opponent gets up once or twice (heavier fighters rise later), so pace
  yourself — stamina drains while guarding and punching.
- Win a fight to unlock the next opponent and location. Progress autosaves
  to one of three save slots.

## Opponents

1. Jessie — Black 22 Boxing Gym, Iloilo City
2. Jevidiah — Citi Hardware, Iloilo City
3. Johnwilt — Jaro Plaza
4. Jereme — Pavia Plaza
5. Daniel — Jollibee Santa Barbara
6. Blacc Twenti Too — Iloilo International Airport
7. Caloy — Caloy's House, the finale

## How the vision pipeline works

```
webcam frame
   -> pose estimation (MediaPipe PoseLandmarker or OpenCV DNN fallback)
   -> body metrics (center, shoulder width, torso height, confidence)
   -> distance estimate (relative: close / medium / far; scales your fighter)
   -> gesture detection
        punch  : wrist depth velocity (3D backend) or arm-extension
                 velocity (2D backend), plus arm-extension checks
        guard  : both wrists near the nose, held briefly
        get-up : both hands raised high for half a second
   -> TrackingData -> FightScene (same dataclass as keyboard mode)
```

The pose backend is chosen automatically at startup:

- **mediapipe** — fast, 3D landmarks. On Windows this is always used; on
  Linux it is first verified in a subprocess self-test, because some
  AMD/Mesa machines deadlock the GPU delegate.
- **cv2** — OpenCV DNN with a YOLO11n-pose model (CPU, ~30 FPS). Deterministic
  and portable; used automatically when MediaPipe is unavailable or unstable.

You can force a choice with `"pose_backend": "auto" | "mediapipe" | "cv2"` in
`saves/settings.json`. Note: `saves/settings.json` in this repository is
machine-local and currently pins `cv2` for the AMD dev box; on other Linux
machines set it back to `auto` so MediaPipe is picked up when its self-test
passes.

Distances are *relative* estimates used for game feel (fighter scale and the
CLOSE / MEDIUM / FAR HUD readout) — they never claim real centimeters.

## Project layout

```
config.py            all tunables: fighters, locations, vision thresholds
core/                game shell, state stack, events, saves, audio, input
camera/              capture, pose tracking (dual backend), calibration,
                     distance, gestures, mediapipe self-test
gameplay/            fighters, AI, combat, hitboxes, progression, tutorial
levels/              location data + procedural backgrounds
ui/                  menu, settings, HUD, screens, fonts, sprites
assets/              fonts, sounds (generated), pose models
tools/               asset setup
main.py              entry point
```

## Known limitations

- The camera pipeline targets a single player in the frame.
- Body-center tracking uses smoothing; very fast dashes may lag a step behind.
- The 2D (cv2) backend estimates punches from arm-extension speed; a sharp,
  fully extended jab triggers it most reliably.

## License

Fonts are bundled under the SIL Open Font License (Liberation Sans). Sounds
are generated at runtime by the game itself. The YOLO11n-pose model is AGPL-3.0
(cf. Ultralytics); the MediaPipe pose model is Apache-2.0.
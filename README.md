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

- Linux or Windows 10/11 (developed and tested on Python 3.11+ / 3.14)
- A webcam (any UVC/V4L2 or DirectShow camera works)
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

## Setup (Windows)

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/) —
   tick **"Add python.exe to PATH"** during setup.
2. Open a terminal (PowerShell or Command Prompt) and clone:

   ```powershell
   git clone https://github.com/Cocoasaur/Pungolay_sa_Panay.git
   cd Pungolay_sa_Panay
   ```

3. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. Install dependencies and fetch the pose models / fonts:

   ```powershell
   pip install -r requirements.txt
   python tools\setup_assets.py
   ```

5. Run the game:

   ```powershell
   python main.py
   ```

`scripts\setup.bat` runs steps 3-5 in one go. Notes:

- Keep `"pose_backend": "auto"` in `saves/settings.json` on Windows — the fast
  3D MediaPipe backend is used there (the AMD/Mesa Linux quirk doesn't apply).
- If the camera feed is black, allow camera access: Windows Settings →
  Privacy & security → Camera → let desktop apps use the camera.
- The first run needs an internet connection to download the pose models.

## How to play

| Action        | Camera gesture                              | Keyboard      |
|---------------|---------------------------------------------|---------------|
| Move          | Deliberate left/right hip movement; keep both hips visible | A / D, ← / → |
| Left punch    | Punch the air with your left hand           | J             |
| Right punch   | Punch the air with your right hand          | K             |
| Guard         | Both hands up near your face (hold)         | Hold Space    |
| Get up        | Both hands raised high (or Space)           | Space         |
| Haymaker      | Hold one bent arm pulled back beside your chest for 5 seconds, then punch | Hold J/K for 5 seconds, release, then tap J/K |
| Recenter      | Reset the body anchor without moving your boxer | R |
| Camera preview | Collapse/expand the small preview | F4 |

Controls and input mode are configurable in **SETTINGS** (also reachable through
Escape → Settings during a fight). Press **F3** for a live debug overlay and **F11** for
fullscreen. If camera movement ever feels reversed, toggle **MIRROR INPUT** in
SETTINGS.

With the OpenCV camera backend, the preview shows a yellow **PUNCH** line in
front of your calibrated side-on stance. It follows your torso and scales with
your camera distance. Extend either hand across it to punch, then bring that
hand back behind the line before punching again. **PUNCH LINE DISTANCE** changes
how far you need to reach; sensitivity remains independent. Recalibrate after changing which direction you face.
Hip movement controls deliberate lateral steps. Camera distance never moves or resizes
the fighter. Both pose backends keep a fixed 240-pixel body height and foreground feet.

## Fight flow

- Opponents can recover twice; their third knockdown is final. Raise both hands
  to recover your own boxer before the count expires.
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

## Responsive controls and camera setup

Settings has three pages: **Controls**, **Camera & Tracking**, and **Audio & Display**.
Use Tab to change pages, arrows to select/change values, or click and drag the
sliders. Back remains visible inside the 1280×720 canvas. Settings writes are
batched for 250 ms and flushed on exit; audio changes keep the camera connected.

The 2D punch line defaults to **75% of calibrated arm length**. Its separate
55–90% distance slider has a live preview. Punch sensitivity adjusts confidence
requirements for 2D crossings and depth thresholds for 3D punches; it never
moves the line. Anatomical **LEFT is cyan** and **RIGHT is orange**, with labels.
Mirror Movement changes movement direction without swapping arm identities.

Camera setup opens immediately, connects and loads tracking in the background,
then guides calibration and punch/block practice. Choose **Start Fight** for the
countdown. Reuse Saved Calibration is explicit. Escape cancels setup; Retry and
Keyboard Mode stay available on failure. Camera Debug returns to its caller;
a fight behind Pause → Settings stays paused. In Debug, **R** toggles raw/filtered
landmarks, **T** retries the camera, and **K** selects keyboard mode.

Hold **one bent arm with its glove pulled back beside your chest** (or **J/K**
in keyboard mode) for **five seconds**. The visible charge area shows the arm
color, progress, remaining time, and corrective hints. The HUD then keeps
**HAYMAKER READY — NEXT PUNCH 2×** visible. The next accepted punch from either arm
uses **2× damage**, even if it misses. Cooldown, hit stun, or knockdown rejection
does not consume readiness. Moving, blocking, tracking loss, and pausing retain
it. Releasing a completed keyboard hold does not attack; tap J or K afterward.
A new fight, retry, result screen, or leaving the fight clears the stored charge.

Capture and inference use independent workers with latest-only slots. Every
pose includes a frame ID and capture/inference timestamps; preview frames stay
paired with their pose. Duplicate renders cannot repeat punches or accelerate
charge, and samples over 250 ms old produce no gesture events. Confident moving
arms use approximately 12 ms smoothing; nearly still arms use 45 ms. Torso/hip
filtering remains steadier to prevent punches from moving the player.

## Stable movement and animation

The body controller uses a three-sample median, a dead zone around the latest
held position, 80 ms movement entry, 150 ms stopping/reacquisition, and outlier
rejection. Speed is bounded by the configured movement speed with 150 ms
acceleration. Small corrections do not become walking steps. **R** rebases the
anchor without changing your world position or saved calibration.

Fighter bodies cannot pass through each other; ordinary approach movement
stops at an eight-pixel body gap. Walking reflects movement after collision
resolution. Knockdowns finish their fall and stay grounded through the count;
get-up is a protected 0.52-second recovery state. Terminal knockouts hold the
fallen frame. The menu and gameplay share the breathing-idle system.

The small camera preview has a visible collapse button and **F4** shortcut;
the preference is saved in Settings → Audio & Display. Frame/pose overlays
rebuild only for fresh samples or changed display options. Animation decoding
and prewarming run in a worker; main-thread uploads have a 2 ms work budget,
and the animation cache is bounded to 128 MiB.

## How the vision pipeline works

```
continuous capture -> latest frame slot
   -> pose estimation (MediaPipe PoseLandmarker or OpenCV DNN fallback)
   -> timestamped matched frame + pose sample
   -> body metrics (center, shoulder width, torso height, confidence)
   -> torso measurements for punch-boundary scale (fighter size remains fixed)
   -> median-filtered hip movement intent: hold / move / tracking lost
   -> gesture detection
        punch  : wrist depth velocity (3D backend) or body-relative
                 boundary crossing (2D backend), plus confidence checks
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
`saves/settings.json`. Note: `saves/settings.json` is machine-local and is
deliberately gitignored — the AMD dev box pins `cv2` for determinism; on
Windows (and other Linux machines where the MediaPipe self-test passes) leave
it at `auto` for the faster 3D backend.

Torso measurements are relative estimates used to position the punch boundary.
Legacy distance/smoothing settings remain readable for save compatibility but
are hidden where they no longer affect gameplay.

## Artwork

The game includes PNG artwork for all seven locations, the player and seven
opponents, the main menu, the pause menu, and the other screens. Artwork is
loaded from the corresponding directories under `assets/`; missing PNGs use
the procedural renderer. No additional asset download is needed for the art.

- `assets/levels/<location_id>.png`: location backgrounds, scaled to 1280 x 720.
- `assets/sprites/<fighter_id>.png`: default fighter images facing right;
  fighters facing left are mirrored automatically. Optional files such as
  `player_punch_l.png` or `jessie_knockdown.png` override individual states.
  Manifest-driven action sheets animate all eight fighters; single PNGs remain
  the fallback for unavailable animations.
- `assets/menu/menu_background_clean.png`: the illustrated gym without baked
  panels, fake window controls, or interface text. All menus render live labels
  and measured boxing-poster controls over the gym.
- `assets/sprites/animations.json`: frame rectangles, neutral body references,
  foot pivots, timing, looping, and final-frame holding. All eight fighters have
  idle, fall, and get-up clips. Daniel's idle reuses existing guard artwork with
  a subtle runtime breathing treatment after imagegen rejected that sheet.
- `assets/sprites/animations/generation-stable.json`: built-in imagegen prompts
  and the exact generated-art/fallback inventory.

Each artwork directory includes editing notes and, where supplied, templates.
Artwork is included in Git. Downloaded models, fonts, generated sounds, local
settings, calibration, and save slots remain ignored and are not imported
from shared project archives.

See [stable movement and poster-interface validation](docs/stable-update-validation.md) for measured
responsiveness, automated checks, replay limitations, and hardware acceptance.

## Project layout

```
config.py            all tunables: fighters, locations, vision thresholds
core/                game shell, state stack, events, saves, audio, input
camera/              capture, pose tracking (dual backend), calibration,
                     distance, gestures, mediapipe self-test
gameplay/            fighters, AI, combat, hitboxes, progression, tutorial
levels/              location data + procedural backgrounds
ui/                  menu, settings, HUD, screens, fonts, sprites
assets/              artwork, fonts, sounds (generated), pose models
tools/               asset setup
main.py              entry point
```

## Known limitations

- The camera pipeline targets a single player in the frame.
- Movement requires confidently visible hips. If hips disappear, the boxer
  freezes and waits for stable reacquisition; the HUD asks you to reposition.
- Recorded inset replays and synthetic tests do not verify live webcam accuracy.
- The 2D backend uses a calibrated body-relative punch line. Keep both hips
  and the punching wrist visible, retract behind the line, then extend past it.

## License

Fonts are bundled under the SIL Open Font License (Liberation Sans). Sounds
are generated at runtime by the game itself. The YOLO11n-pose model is AGPL-3.0
(cf. Ultralytics); the MediaPipe pose model is Apache-2.0.

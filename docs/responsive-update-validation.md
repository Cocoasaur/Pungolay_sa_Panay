# Responsive tracking and animated fighters — validation

Validated 4 November 2026 against baseline `b21b6b0` on `drive-assets-update`.
`main` is outside this change. The game keeps its existing maps, character
identities, 240-pixel neutral fighter-height reference, and GROUND_Y=620.

## Automated verification

Run from the repository with its existing environment:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -B -m unittest discover -s tests -q
```

The expanded suite has **82 tests** (41 previously). Coverage includes:

- Fast arms reach at least 90% of a confident jump within two fresh 60 FPS
  samples; idle jitter, occluded wrists, impossible limbs, crossed anatomical
  arms, mirror movement, 2D crossings, and existing 3D depth detection.
- Independent punch-line distance, outward placement, body following,
  temporary missing hips, immediate crossings, and retraction before rearming.
- Matched frame/pose publication, superseded-frame drops, duplicate events,
  stale-sample rejection, and duplicate charge samples not advancing timers.
- Five-second charge completion, either-arm consumption, missed attacks,
  cooldown/hit/knockdown rejection, immutable damage snapshots, return to
  normal damage, keyboard hold/release behavior, and sustained guard.
- All 144 frame rectangles and foot pivots, transparent sheets, grounded
  soles, distinct punch phases, enemy attack duration, and stationary idle.
- Settings/Debug/Calibration return contexts, paused-fight preservation,
  cancellation and keyboard fallback, final-victory buttons, bounded retries,
  visible controls, sliders, debounce, and opaque/transparent scene drawing.
- Slow device opening, slow initialization, failed devices not being reopened
  on every render, cancellation ignoring late results, and active-device scans.
  A camera open delayed over one second leaves screen drawing and Escape active.

## Measured response

These are **headless CPU construction-and-draw measurements**, with the game's
installed Liberation Sans fonts. They exclude display/vsync and operating-system
input latency. Each screen was constructed and drawn 25 times using cached art.

| Screen | Median | Maximum |
|---|---:|---:|
| Settings | 0.35 ms | 2.23 ms |
| Pause | 0.92 ms | 10.99 ms |
| Camera Debug | 0.39 ms | 8.03 ms |
| Calibration | 0.30 ms | 8.32 ms |

With device discovery deliberately delayed 1,100 ms, baseline Settings took
**1,101.82 ms** to construct and draw. The new screen took **0.69 ms** with the
same delayed probe installed: it reads cached devices without invoking it.
These measurements meet the 100 ms CPU display-work target in this environment.

Reproduce benchmarks and Settings before/after PNGs:

```sh
python -B tools/benchmark_ui.py --output /tmp/pungolay-ui-benchmark
```

## Recorded punch replay

Replayed the existing 54.9-second screen recording's camera inset using the
local OpenCV DNN model. The tool samples every fifth 60 FPS video frame and
uses recording timestamps for filtering; inference is timed separately.
It exports numerical metrics only, without copying personal camera footage.

| Measurement | Result |
|---|---:|
| Samples / samples with a present pose | 659 / 574 |
| Replay sampling rate | 12 Hz |
| Inference median / 95th percentile | 26.87 / 31.48 ms |
| Confident wrist samples / fast samples | 1,004 / 470 |
| Mean wrist distance from measured landmarks, old filter | 0.07233 normalized units |
| Mean wrist distance from measured landmarks, new filter | 0.00202 normalized units |
| Fast-motion mean distance, old / new | 0.10804 / 0.00027 |

The recording contains a small camera inset with old tracking graphics baked
in. These results measure inference/filter behavior; they do **not** establish
live latency, anatomical identity accuracy, or ground-truth punch accuracy.
The independent synthetic 60 FPS step test reaches approximately **93.8%** of a
confident fast movement after two samples, compared with **9.75%** for two
applications of the old large-jump 5% filter.

```sh
python -B tools/benchmark_tracking.py /path/to/recording.mp4 \
  --model assets/models/yolo11n-pose.onnx --output /tmp/tracking-metrics.json
```

The default ROI fits this existing 2560×1600 screen recording. Pass `--roi
x,y,width,height` for another layout. MediaPipe depth behavior is regression
tested with 3D landmark fixtures; recorded inference here uses OpenCV.

## Artwork and visual review

Built-in imagegen generated **48 transparent action sheets**, using each of
the original eight fighter PNGs as its identity reference. Six action clips
per fighter provide **18 frames each / 144 total**. The full prompt set and
mode are in `assets/sprites/animations/generation.json`.

Review covered each used cell for identity, clothing, limbs, clipping, and
frame-size changes. Automated checks found no used-frame edge contacts and
transparent pixels in every used cell. Uniform grid-cell bounds exclude
unused-cell artifacts. A shared reference scale per fighter and explicit sole
pivots avoid independent frame cropping/scaling and keep the feet grounded.
Attack frames follow active hitbox timing; walking follows actual movement.

Screenshots reviewed the main menu, all Settings tabs, connection/calibration/
practice/failure states, Debug, load, level selection, Pause, defeat, victory,
and final victory. All eight fighters were reviewed against all seven maps.
The eight-fighter contact views use 80% scale to fit the entire roster;
ordinary gameplay preserves the 240-pixel neutral reference.

Before/after Settings views, map/roster contacts, all action-frame contacts,
and an animation GIF were delivered as local preview artifacts. Personal
recordings, camera images, saves, calibration, models, virtual environments,
and downloaded fonts are excluded from commits.

## Hardware acceptance still required

No accessible webcam device is exposed to this execution environment, so live
webcam comparison and actual desktop input-to-display timing remain unverified.
On the target machine:

1. Open Camera & Tracking and confirm Connecting/Loading Tracking appears
   immediately, with responsive Back/Escape throughout initialization.
2. Calibrate and practice each arm and block, then explicitly Start Fight.
   Check that cyan LEFT and orange RIGHT remain anatomical when arms cross.
3. In Debug, compare raw and filtered landmarks with R while punching quickly.
   Read inference time and sample age separately; retract behind the line.
4. Confirm punching does not advance the fighter. Test tracking loss/recovery,
   either-arm charged punches, sustained guard, and keyboard hold/release.
5. Confirm Pause → Settings → Debug → Escape → Settings → Escape → Pause;
   cancel recalibration and confirm the paused fight stays paused.

The implementation, automated suite, replay, and headless visual/performance
checks are complete; these live hardware acceptance checks remain explicit.

"""Repeatable software screen/draw benchmarks, with optional baseline checkout.

Example: python tools/benchmark_presentation.py --repo /path/to/checkout --output /tmp/ui
No device is opened; saves live in a disposable directory. This does not measure
vsync/display latency, camera inference, or total live FPS.
"""

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", default="/tmp/presentation-benchmark")
    args = parser.parse_args()
    sys.path.insert(0, args.repo)
    import pygame, config
    from core.game import Game
    from ui.main_menu import MainMenu
    from ui.settings import SettingsScene
    from ui.pause_menu import PauseMenu
    from ui.screens import CameraDebugView, CalibrationScreen

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    try:
        from ui.animation_cache import cache
    except ImportError:
        cache = None

    def pump():
        if cache:
            cache.pump()

    with tempfile.TemporaryDirectory() as temp, patch.object(
        config, "SAVES_DIR", temp
    ), patch.object(config, "SETTINGS_PATH", temp + "/settings.json"), patch(
        "core.game.AudioManager"
    ):
        game = Game()
        result = {}
        try:
            if cache:
                cache.wait_ready(30)
            game.states.draw(game.canvas)
            pygame.image.save(game.canvas, str(out / "main-menu.png"))
            for name, factory in [
                ("main", MainMenu),
                ("settings", SettingsScene),
                ("pause", PauseMenu),
                ("debug", CameraDebugView),
                ("calibration", CalibrationScreen),
            ]:
                times = []
                for _ in range(30):
                    start = time.perf_counter()
                    scene = factory(game)
                    scene.draw(game.canvas)
                    times.append((time.perf_counter() - start) * 1000)
                result[name] = {
                    "median_ms": round(statistics.median(times), 2),
                    "max_ms": round(max(times), 2),
                }
            game.settings["input_mode"] = "keyboard"
            game.start_new_game()
            fight = game.states.current
            fight.intro_timer = 0
            fight.tutorial.active = False
            if cache:
                cache.wait_ready(30)
            fight.draw(game.canvas)
            pygame.image.save(game.canvas, str(out / "gameplay.png"))
            times = []
            for i in range(240):
                start = time.perf_counter()
                pump()
                fight.draw(game.canvas)
                times.append((time.perf_counter() - start) * 1000)
            result["fight_draw"] = {
                "median_ms": round(statistics.median(times), 2),
                "p95_ms": round(sorted(times)[228], 2),
                "max_ms": round(max(times), 2),
            }
            if cache:
                result["animation_cache_bytes"] = cache.memory_bytes
                from ui.animation import prewarm_pair
                cache.cancel()
                start=time.perf_counter()
                prewarm_pair(("player",1),(game.progression.opponent_id,-1))
                result["prewarm_request_ms"]=round((time.perf_counter()-start)*1000,2)
                cold=[];navigation=[];peak=0;deadline=time.monotonic()+15
                while cache.pending and time.monotonic()<deadline:
                    start=time.perf_counter();cache.pump();fight.draw(game.canvas)
                    cold.append((time.perf_counter()-start)*1000)
                    start=time.perf_counter();SettingsScene(game).draw(game.canvas)
                    navigation.append((time.perf_counter()-start)*1000)
                    peak=max(peak,cache.memory_bytes);time.sleep(.001)
                result["during_prewarm"]={"samples":len(cold),"draw_max_ms":round(max(cold,default=0),2),"settings_max_ms":round(max(navigation,default=0),2),"sampled_cache_peak_bytes":peak,"all_frames_ready":not cache.pending}
            # Matched synthetic camera frame and landmarks; no camera is opened.
            import numpy as np
            from camera.pose_tracker import PoseData
            game.settings["input_mode"]="camera"
            game.last_camera_frame=np.zeros((360,640,3),dtype=np.uint8)
            game.last_pose=PoseData(present=False)
            for mode in ("duplicate","fresh"):
                timings=[]
                for i in range(120):
                    game.tracking.sample_id=i if mode=="fresh" else 0
                    start=time.perf_counter();fight.draw(game.canvas)
                    timings.append((time.perf_counter()-start)*1000)
                result["camera_preview_"+mode]={"median_ms":round(statistics.median(timings),2),"max_ms":round(max(timings),2)}
        finally:
            game.shutdown()
    result["limitations"] = (
        "Headless software construction/drawing; excludes display flip, vsync, input-device latency and inference. Cached page transitions should remain below 100 ms."
    )
    (out / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

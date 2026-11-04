"""Headless transition benchmarks and before/after PNGs; no camera is opened."""

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import types
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame
import config
from core.game import Game
from ui.settings import SettingsScene
from ui.screens import CameraDebugView, CalibrationScreen
from ui.pause_menu import PauseMenu


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/pungolay-ui-benchmark")
    parser.add_argument("--baseline", default="b21b6b0")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, patch.object(
        config, "SAVES_DIR", temp
    ), patch.object(config, "SETTINGS_PATH", temp + "/settings.json"), patch(
        "core.game.AudioManager"
    ):
        game = Game()
        results = {}
        try:
            for name, factory in [
                ("settings", SettingsScene),
                ("pause", PauseMenu),
                ("debug", CameraDebugView),
                ("calibration", CalibrationScreen),
            ]:
                samples = []
                for _ in range(25):
                    start = time.perf_counter()
                    scene = factory(game)
                    scene.draw(game.canvas)
                    samples.append((time.perf_counter() - start) * 1000)
                results[name] = {
                    "median_ms": round(statistics.median(samples), 2),
                    "max_ms": round(max(samples), 2),
                }
            for tab in range(3):
                scene = SettingsScene(game)
                scene.tab = tab
                scene._build_rows()
                scene.draw(game.canvas)
                pygame.image.save(game.canvas, str(out / f"settings-after-{tab}.png"))
            # The baseline did hardware discovery inside the constructor.
            source = subprocess.check_output(
                ["git", "show", args.baseline + ":ui/settings.py"], text=True
            )
            baseline = types.ModuleType("baseline_settings")
            exec(compile(source, "baseline_settings", "exec"), baseline.__dict__)

            def slow_probe():
                time.sleep(1.1)
                return [0]

            with patch.object(baseline, "probe_cameras", side_effect=slow_probe):
                start = time.perf_counter()
                old = baseline.SettingsScene(game)
                old.draw(game.canvas)
                results["baseline_settings_with_1100ms_scan_ms"] = round(
                    (time.perf_counter() - start) * 1000, 2
                )
            pygame.image.save(game.canvas, str(out / "settings-before.png"))
            with patch("ui.settings.probe_cameras", side_effect=slow_probe):
                start = time.perf_counter()
                SettingsScene(game).draw(game.canvas)
                results["new_settings_with_same_slow_probe_ms"] = round(
                    (time.perf_counter() - start) * 1000, 2
                )
        finally:
            game.shutdown()
    (out / "metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

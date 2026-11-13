"""Render fight-HUD review states with synthetic camera data and disposable saves.

Use --repo to capture a baseline checkout with the identical scene fixture.
No camera is opened and no personal recording or saved progress is read.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.path.insert(0, args.repo)
    import numpy as np
    import pygame
    import config
    from core.game import Game
    from core.tracking import TrackingData
    from camera.pose_tracker import PoseData
    from ui.animation_cache import cache
    from ui.fonts import load_fonts
    from ui import theme

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, patch.object(
        config, "SAVES_DIR", temp
    ), patch.object(config, "SETTINGS_PATH", temp + "/settings.json"), patch(
        "core.game.AudioManager"
    ):
        game = Game()
        try:
            game.settings["input_mode"] = "keyboard"
            game.start_new_game()
            fight = game.states.current
            fight.intro_timer = 0
            fight.tutorial.active = False
            cache.wait_ready(30)
            # Synthetic unoccupied camera frame: never use personal imagery.
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
            frame[:] = (64, 54, 46)
            game.last_camera_frame = frame
            game.last_pose = PoseData(present=False)
            game.settings["input_mode"] = "camera"
            fight.player.x, fight.enemy.x = 704, 972
            fight.player.hp, fight.enemy.hp = 75, 35

            def capture(name, data=None, ready=False, visible=True, tutorial=False):
                game.last_tracking = game.tracking = data or TrackingData(pose_present=True)
                fight.player.ability_ready = ready
                game.settings["camera_preview"] = visible
                fight.tutorial.active = tutorial
                fight.draw(game.canvas)
                pygame.image.save(game.canvas, str(out / (name + ".png")))

            # Count changed pixels against a solid arena, excluding fighters.
            # This measures reserved UI area, not subjective readability.
            coverage = {}
            for name, camera, practice, warning in (
                ("hud_only", False, False, False),
                ("camera_visible", True, False, False),
                ("tutorial", True, True, False),
                ("tracking_warning", True, False, True),
            ):
                canvas = pygame.Surface((1280, 720))
                canvas.fill((89, 131, 167))
                data = TrackingData(
                    pose_present=True, movement_status="TRACKING LOST" if warning else "HOLDING"
                )
                fight.hud.draw(canvas, fight.player, fight.enemy, tracking=data)
                if camera:
                    fight._draw_camera_preview(canvas)
                if practice:
                    fight._draw_tutorial(canvas)
                unchanged = np.all(pygame.surfarray.array3d(canvas) == (89, 131, 167), axis=2)
                coverage[name] = {
                    "arena_untouched_percent": round(float(unchanged.mean() * 100), 2)
                }
            (out / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
            capture("idle")
            capture(
                "charging-left",
                TrackingData(
                    is_charging=True,
                    charge_progress=0.6,
                    charge_side="left",
                    charge_hint="Keep your glove pulled back",
                    pose_present=True,
                ),
            )
            capture(
                "charging-right",
                TrackingData(
                    is_charging=True, charge_progress=0.8, charge_side="right", pose_present=True
                ),
            )
            capture("ready", ready=True)
            capture(
                "tracking-lost", TrackingData(movement_status="TRACKING LOST", pose_present=True)
            )
            capture("collapsed", visible=False)
            capture("tutorial", tutorial=True)
            game.settings["input_mode"] = "keyboard"
            capture("keyboard")
            game.settings["input_mode"] = "camera"
            # Arena and opponent coverage at the same 240-pixel fighter size.
            for index, name in enumerate(config.OPPONENT_ORDER):
                game.progression.start_fight(index)
                fight._reset_for_opponent()
                fight.intro_timer = 0
                fight.tutorial.active = False
                from ui.animation import prewarm_pair

                prewarm_pair(("player", 1), (name, -1))
                cache.wait_ready(30)
                capture("arena-" + game.progression.location_id)
            game.progression.start_fight(0)
            fight._reset_for_opponent()
            fight.intro_timer = 0
            with patch.object(config, "FONTS_DIR", "/tmp/no-fonts-here"):
                theme.fitted.cache_clear()
                game.fonts = load_fonts()
                fight._preview_key = None
                fight.hud.fonts = game.fonts
                capture("fallback-fonts", ready=True, tutorial=True)
            theme.fitted.cache_clear()
            # Match Game.run's letterbox projection for common window sizes.
            game.fonts = load_fonts()
            fight._preview_key = None
            fight.hud.fonts = game.fonts
            capture("window-source", ready=True)
            for w, h in ((960, 540), (1280, 720), (1920, 1080), (758, 905)):
                window = pygame.Surface((w, h))
                ratio = min(w / 1280, h / 720)
                size = (round(1280 * ratio), round(720 * ratio))
                image = pygame.transform.smoothscale(game.canvas, size)
                window.blit(image, image.get_rect(center=(w // 2, h // 2)))
                pygame.image.save(window, str(out / f"window-{w}x{h}.png"))
        finally:
            game.shutdown()
    pygame.font.init()
    # Review contact sheets preserve the originals alongside them.
    for name, filenames in (
        ("arenas", sorted(out.glob("arena-*.png"))),
        (
            "states",
            [
                out / (name + ".png")
                for name in (
                    "idle",
                    "charging-left",
                    "charging-right",
                    "ready",
                    "tracking-lost",
                    "collapsed",
                    "tutorial",
                    "fallback-fonts",
                )
            ],
        ),
        ("windows", sorted(out.glob("window-*x*.png"))),
    ):
        sheet = pygame.Surface((1280, ((len(filenames) + 1) // 2) * 384))
        sheet.fill((23, 21, 18))
        font = pygame.font.Font(None, 22)
        for i, path in enumerate(filenames):
            x, y = (i % 2) * 640, (i // 2) * 384
            image = pygame.image.load(str(path))
            ratio = min(640 / image.get_width(), 360 / image.get_height())
            image = pygame.transform.smoothscale(
                image, (round(image.get_width() * ratio), round(image.get_height() * ratio))
            )
            sheet.blit(image, image.get_rect(midtop=(x + 320, y + 24)))
            sheet.blit(font.render(path.stem, True, (242, 231, 211)), (x + 8, y + 3))
        pygame.image.save(sheet, str(out / (name + ".png")))
    print("Saved HUD review captures to", out)


if __name__ == "__main__":
    main()

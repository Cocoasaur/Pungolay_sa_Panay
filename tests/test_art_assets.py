"""Asset selection, transparency, resizing, and procedural fallback checks."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import config
from gameplay.progression import Progression
from levels.level_manager import LevelManager
from ui.backgrounds import build_menu_background
from ui.fonts import load_fonts
from ui.main_menu import MainMenu
from ui.screens import _load_screen_overlay
from ui.sprites import _load_sprite, _scaled_sprite, _sprite_path, draw_boxer


class ArtAssetTests(unittest.TestCase):
    def setUp(self):
        drivers = patch.dict(os.environ, {
            "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
        })
        drivers.start()
        self.addCleanup(drivers.stop)
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((config.BASE_WIDTH, config.BASE_HEIGHT))
        self.addCleanup(pygame.quit)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        _load_sprite.cache_clear()
        _scaled_sprite.cache_clear()
        self.addCleanup(_load_sprite.cache_clear)
        self.addCleanup(_scaled_sprite.cache_clear)

    def image(self, name, color, size=(4, 4)):
        path = self.temp / name
        image = pygame.Surface(size, pygame.SRCALPHA)
        image.fill(color)
        pygame.image.save(image, str(path))
        return str(path)

    def test_campaign_artwork_matches_location_and_fighter_ids(self):
        for location in config.LOCATION_ORDER:
            with self.subTest(location=location):
                image = pygame.image.load(str(Path(config.LEVELS_DIR) / f"{location}.png"))
                self.assertEqual(image.get_size(), (config.BASE_WIDTH, config.BASE_HEIGHT))
        for fighter in ["player", *config.OPPONENT_ORDER]:
            with self.subTest(fighter=fighter):
                path = _sprite_path(fighter, "idle")
                self.assertIsNotNone(path)
                self.assertEqual(Path(path).stem, fighter)
                image = _load_sprite(path)
                self.assertGreater(image.get_bounding_rect().height, 0)

    def test_specific_action_and_shared_enemy_sprite_fallbacks(self):
        with patch.object(config, "SPRITES_DIR", str(self.temp)):
            default = self.image("jessie.png", "red")
            shared = self.image("enemy_attack.png", "green")
            self.assertEqual(_sprite_path("jessie", "idle"), default)
            self.assertEqual(_sprite_path("jessie", "attack"), shared)
            specific = self.image("jessie_attack.png", "blue")
            self.assertEqual(_sprite_path("jessie", "attack"), specific)
            Path(specific).unlink()
            Path(shared).unlink()
            Path(default).unlink()
            self.assertIsNone(_sprite_path("jessie", "attack"))
            surface = pygame.Surface((400, 300))
            for state in ("idle", "punch_l", "punch_r", "guard", "hit", "knockdown", "ko"):
                draw_boxer(surface, 200, 200, 1, state, 0, 1, (80, 30, 30),
                           fighter_id="jessie")

    def test_fighter_mirroring_and_flash_keep_transparent_pixels_clear(self):
        image = pygame.Surface((4, 4), pygame.SRCALPHA)
        image.fill((255, 0, 0, 255), (1, 1, 1, 3))
        image.fill((0, 0, 255, 255), (2, 1, 1, 3))
        path = self.temp / "player.png"
        pygame.image.save(image, str(path))
        with patch.object(config, "SPRITES_DIR", str(self.temp)):
            normal = _scaled_sprite(str(path), 4, 4, 1)
            mirrored = _scaled_sprite(str(path), 4, 4, -1)
            self.assertEqual(normal.get_at((1, 1)), mirrored.get_at((2, 1)))
            before = pygame.image.tobytes(normal, "RGBA")
            canvas = pygame.Surface((400, 300))
            canvas.fill((10, 20, 30))
            draw_boxer(canvas, 200, 200, 1, "hit", 0, 1, (80, 30, 30), flash=True)
            self.assertEqual(canvas.get_at((141, 81))[:3], (10, 20, 30))
            self.assertEqual(pygame.image.tobytes(normal, "RGBA"), before)

    def test_custom_arena_resizes_composites_and_caches(self):
        path = self.temp / "black22.png"
        image = pygame.Surface((2, 2), pygame.SRCALPHA)
        image.fill((220, 40, 30, 255), (0, 0, 1, 2))
        pygame.image.save(image, str(path))
        background = pygame.Surface((config.BASE_WIDTH, config.BASE_HEIGHT))
        background.fill((20, 40, 60))
        with patch.object(config, "LEVELS_DIR", str(self.temp)), patch(
                "levels.level_manager.build_arena_background", return_value=background) as build:
            levels = LevelManager(Progression())
            loaded = levels.background("black22")
            self.assertEqual(loaded.get_at((0, 0))[:3], (220, 40, 30))
            self.assertEqual(loaded.get_at((config.BASE_WIDTH - 1, 0))[:3], (20, 40, 60))
            self.assertIs(levels.background("black22"), loaded)
            build.assert_called_once()

    def test_missing_arena_and_menu_art_use_procedural_backgrounds(self):
        with patch.object(config, "LEVELS_DIR", str(self.temp)), patch.object(
                config, "MENU_BACKGROUND_PATH", str(self.temp / "missing.png")):
            levels = LevelManager(Progression())
            expected = (config.BASE_WIDTH, config.BASE_HEIGHT)
            self.assertEqual(levels.background().get_size(), expected)
            self.assertEqual(build_menu_background().get_size(), expected)

    def test_custom_menu_background_takes_priority_over_legacy_overlay(self):
        custom = self.image("background.png", "red")
        overlay = self.image("menu.png", "blue")
        with patch.object(config, "MENU_BACKGROUND_PATH", custom), patch.object(
                config, "MENU_IMAGE_PATH", overlay):
            game = SimpleNamespace(fonts=load_fonts())
            menu = MainMenu(game)
            self.assertEqual(menu.background.get_size(), (config.BASE_WIDTH, config.BASE_HEIGHT))
            self.assertEqual(menu.background.get_at((0, 0))[:3], (255, 0, 0))
            self.assertIsNone(menu.menu_overlay)
            Path(custom).unlink()
            fallback = MainMenu(game)
            self.assertIsNotNone(fallback.menu_overlay)

    def test_optional_screen_overlay_resizes_and_preserves_alpha(self):
        with patch.object(config, "SCREENS_DIR", str(self.temp)):
            self.assertIsNone(_load_screen_overlay("settings"))
            self.image("settings.png", (30, 40, 50, 80))
            overlay = _load_screen_overlay("settings")
            self.assertEqual(overlay.get_size(), (config.BASE_WIDTH, config.BASE_HEIGHT))
            self.assertEqual(overlay.get_at((0, 0)), (30, 40, 50, 80))


if __name__ == "__main__":
    unittest.main()

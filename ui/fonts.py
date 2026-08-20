"""Font loading with graceful fallbacks.

Prefers the bundled Liberation Sans (OFL) so the game looks identical on any
machine; falls back to system fonts and finally to pygame's built-in font.
"""

from __future__ import annotations

import os
from typing import Dict

import pygame

import config


def _candidates() -> list:
    paths = [
        os.path.join(config.FONTS_DIR, "LiberationSans-Bold.ttf"),
        os.path.join(config.FONTS_DIR, "LiberationSans-Regular.ttf"),
        os.path.join(config.FONTS_DIR, "LiberationSans-Italic.ttf"),
    ]
    return [p for p in paths if os.path.exists(p)]


def load_fonts() -> Dict[str, pygame.font.Font]:
    """Returns a dict of named font objects at the sizes the UI needs."""
    fonts: Dict[str, pygame.font.Font] = {}
    sizes = {"tiny": 13, "small": 16, "medium": 22, "large": 34,
             "big": 64, "huge": 150}
    regular = bold = None

    for path in _candidates():
        if "Bold" in path and bold is None:
            bold = path
        elif regular is None:
            regular = path

    for name, size in sizes.items():
        use_bold = name in ("large", "big", "huge")
        path = bold if (use_bold and bold) else (regular or bold)
        if path:
            fonts[name] = pygame.font.Font(path, size)
        else:
            # fall back to pygame's default font (never None)
            fonts[name] = pygame.font.Font(None, size)
    return fonts


def render_spaced(text: str, font: pygame.font.Font, color, spacing: int = 6):
    """Render text with extra letter spacing (for titles and menu labels)."""
    surfaces = [font.render(ch, True, color) for ch in text]
    width = sum(s.get_width() for s in surfaces) + spacing * (len(surfaces) - 1)
    height = max(s.get_height() for s in surfaces)
    out = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
    x = 0
    for surf in surfaces:
        out.blit(surf, (x, 0))
        x += surf.get_width() + spacing
    return out
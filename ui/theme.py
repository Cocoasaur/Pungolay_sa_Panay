"""Measured native boxing-poster primitives. All controls and text stay live."""

from functools import lru_cache
from pathlib import Path
import pygame
import config
from ui.fonts import cached_text


@lru_cache(maxsize=128)
def fitted(text, width, size=22, bold=False, spacing=0):
    name = "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
    path = Path(config.FONTS_DIR) / name
    for actual in range(size, 11, -1):
        font = pygame.font.Font(str(path) if path.is_file() else None, actual)
        if (sum(font.size(c)[0] for c in text) if spacing else font.size(text)[0]) + max(
            0, len(text) - 1
        ) * spacing <= width:
            return font
    return font


def text(surface, fonts, value, pos, color=None, size="small"):
    image = cached_text(fonts[size], str(value), color or config.COLORS["text"])
    surface.blit(image, pos)
    return image.get_rect(topleft=pos)


@lru_cache(maxsize=4)
def backdrop(size=(1280, 720)):
    from ui.backgrounds import build_menu_background

    image = pygame.transform.smoothscale(build_menu_background(), size).copy()
    shade = pygame.Surface(size, pygame.SRCALPHA)
    shade.fill((15, 13, 10, 235))
    image.blit(shade, (0, 0))
    pygame.draw.rect(image, (184, 58, 43), (0, 0, 12, size[1]))
    pygame.draw.line(image, (86, 74, 61), (44, 120), (size[0] - 44, 120), 1)
    pygame.draw.line(image, (86, 74, 61), (44, size[1] - 28), (size[0] - 44, size[1] - 28), 1)
    return image


def background(surface):
    surface.blit(backdrop(surface.get_size()), (0, 0))


def panel(surface, rect, accent=False):
    pygame.draw.rect(surface, (31, 28, 24), rect, border_radius=3)
    pygame.draw.rect(surface, (100, 85, 66), rect, 1, border_radius=3)
    if accent:
        pygame.draw.rect(surface, (184, 58, 43), (rect.x, rect.y, 5, rect.h))


def button(surface, rect, label, selected=False, primary=False, disabled=False):
    fill = (184, 58, 43) if (primary or selected) and not disabled else (39, 35, 29)
    pygame.draw.rect(surface, fill, rect, border_radius=3)
    pygame.draw.rect(
        surface,
        (242, 231, 211) if selected and not disabled else (100, 85, 66),
        rect,
        2 if selected else 1,
        border_radius=3,
    )
    font = fitted(label, rect.w - 28, 22, True)
    image = cached_text(font, label, (119, 109, 96) if disabled else (242, 231, 211))
    surface.blit(image, image.get_rect(center=rect.center))

"""Location backgrounds: procedurally painted arena backdrops.

Each of the seven locations gets a simple, visually distinct backdrop painted
once into a cached surface: a wall gradient, location-specific props, and the
shared boxing ring (floor boards, corner posts, ropes) in front.
"""

from __future__ import annotations

import math

import pygame

import config


def _gradient_rect(surface: pygame.Surface, rect: pygame.Rect,
                   top: tuple, bottom: tuple) -> None:
    """Vertical gradient between two colors over a rect."""
    h = rect.height
    for i in range(h):
        t = i / max(1, h - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(surface, color, (rect.x, rect.y + i),
                         (rect.x + rect.right - 1, rect.y + i))


def build_arena_background(location: dict) -> pygame.Surface:
    """Paint and cache the arena backdrop for one location."""
    surface = pygame.Surface((config.BASE_WIDTH, config.BASE_HEIGHT))
    wall = location["wall"]
    wall_top = location["wall_top"]
    floor = location["floor"]

    # -- upper wall -----------------------------------------------------
    wall_rect = pygame.Rect(0, 0, config.BASE_WIDTH, config.RING_FLOOR_Y)
    _gradient_rect(surface, wall_rect, wall_top, wall)

    # horizontal wall seam lines for an industrial feel
    seam = tuple(max(0, c - 26) for c in wall)
    for y in (140, 260, 360):
        pygame.draw.line(surface, seam, (0, y), (config.BASE_WIDTH, y), 2)

    # -- location-specific props ----------------------------------------
    props = location.get("props", [])
    for prop in props:
        painter = _PROPS.get(prop)
        if painter:
            painter(surface, wall, wall_top)

    # -- ring floor -----------------------------------------------------
    floor_rect = pygame.Rect(0, config.RING_FLOOR_Y, config.BASE_WIDTH,
                             config.BASE_HEIGHT - config.RING_FLOOR_Y)
    _gradient_rect(surface, floor_rect, floor, tuple(max(0, c - 34) for c in floor))
    plank = tuple(max(0, c - 18) for c in floor)
    for y in range(config.RING_FLOOR_Y + 8, config.BASE_HEIGHT, 16):
        pygame.draw.line(surface, plank, (0, y), (config.BASE_WIDTH, y), 2)
    for x in range(0, config.BASE_WIDTH, 96):
        pygame.draw.line(surface, plank, (x, config.RING_FLOOR_Y + 8),
                         (x, config.BASE_HEIGHT), 2)

    # -- boxing ring ropes and posts ------------------------------------
    rope_dark = (40, 34, 30)
    rope_light = (92, 80, 70)
    for y in config.ROPE_YS:
        pygame.draw.line(surface, rope_dark, (0, y), (config.BASE_WIDTH, y), 8)
        pygame.draw.line(surface, rope_light, (0, y), (config.BASE_WIDTH, y), 3)
    post_color = (70, 58, 48)
    for x in (config.RING_POST_X, config.BASE_WIDTH - config.RING_POST_X):
        pygame.draw.rect(surface, post_color,
                         (x - 7, min(config.ROPE_YS) - 12, 14,
                          config.RING_FLOOR_Y - min(config.ROPE_YS) + 30))
        pygame.draw.circle(surface, tuple(max(0, c + 30) for c in post_color),
                           (x, min(config.ROPE_YS) - 12), 11)

    # subtle vignette
    vignette = pygame.Surface((config.BASE_WIDTH, config.BASE_HEIGHT),
                              pygame.SRCALPHA)
    for i in range(90):
        alpha = int(28 * (1 - i / 90))
        pygame.draw.rect(vignette, (0, 0, 0, alpha), (i, i,
                         config.BASE_WIDTH - 2 * i, config.BASE_HEIGHT - 2 * i),
                         width=2)
    surface.blit(vignette, (0, 0))
    return surface


# ---------------------------------------------------------------------------
# prop painters: each draws a few simple shapes into the wall area
# ---------------------------------------------------------------------------
def _paint_gym(surface, wall, wall_top):
    dark = tuple(max(0, c - 40) for c in wall)
    # banner
    pygame.draw.rect(surface, (150, 60, 44), (300, 60, 420, 64))
    pygame.draw.rect(surface, (110, 42, 30), (300, 60, 420, 64), 3)
    # dumbbell rack silhouettes
    for i, x in enumerate((560, 700, 840)):
        pygame.draw.rect(surface, dark, (x, 300, 90, 130))
        for j in range(3):
            pygame.draw.circle(surface, dark, (x + 12, 330 + j * 36), 9)
            pygame.draw.circle(surface, dark, (x + 78, 330 + j * 36), 9)


def _paint_shelves(surface, wall, wall_top):
    dark = tuple(max(0, c - 34) for c in wall)
    for shelf_x in (120, 620, 980):
        pygame.draw.rect(surface, dark, (shelf_x, 200, 160, 280))
        for y in range(240, 460, 44):
            pygame.draw.line(surface, tuple(min(255, c + 20) for c in dark),
                             (shelf_x, y), (shelf_x + 160, y), 4)
    # hanging tools
    for x in (420, 450, 480):
        pygame.draw.line(surface, (200, 160, 70), (x, 150), (x, 190), 3)


def _paint_plaza(surface, wall, wall_top):
    # arches
    arch = tuple(max(0, c - 28) for c in wall)
    for x in (200, 560, 920):
        pygame.draw.rect(surface, arch, (x, 120, 150, 380))
        pygame.draw.circle(surface, wall_top, (x + 75, 120), 75)
    # lamp posts
    for x in (420, 860):
        pygame.draw.line(surface, (90, 90, 110), (x, 160), (x, 480), 6)
        pygame.draw.circle(surface, (230, 210, 150), (x, 150), 14)


def _paint_plaza_palma(surface, wall, wall_top):
    _paint_plaza(surface, wall, wall_top)
    # palm silhouettes
    green = (60, 90, 50)
    for x in (140, 1140):
        pygame.draw.line(surface, (70, 60, 40), (x, 480), (x + 20, 280), 8)
        for ang in range(-60, 61, 30):
            rad = math.radians(ang)
            end = (x + 20 + math.sin(rad) * 70, 280 - math.cos(rad) * 26)
            pygame.draw.line(surface, green, (x + 20, 280), end, 6)


def _paint_fastfood(surface, wall, wall_top):
    # red/yellow facade
    pygame.draw.rect(surface, (170, 44, 36), (200, 120, 880, 120))
    pygame.draw.rect(surface, (210, 160, 60), (200, 240, 880, 26))
    for x in (260, 460, 660, 860):
        pygame.draw.rect(surface, (140, 110, 60), (x, 300, 130, 180))
        pygame.draw.rect(surface, (90, 70, 40), (x + 8, 308, 114, 164))


def _paint_airport(surface, wall, wall_top):
    # glass panels
    glass = tuple(min(255, c + 30) for c in wall)
    for x in range(60, 1220, 180):
        pygame.draw.rect(surface, glass, (x, 130, 150, 350))
        pygame.draw.line(surface, wall_top, (x + 75, 130), (x + 75, 480), 4)
    # runway lights
    for x in range(0, config.BASE_WIDTH, 60):
        pygame.draw.circle(surface, (150, 190, 220), (x, config.RING_FLOOR_Y + 24), 5)


def _paint_living_room(surface, wall, wall_top):
    dark = tuple(max(0, c - 30) for c in wall)
    # picture frames
    for x in (220, 420, 840):
        pygame.draw.rect(surface, (120, 90, 60), (x, 150, 120, 90))
        pygame.draw.rect(surface, (80, 60, 44), (x, 150, 120, 90), 4)
    # sofa
    pygame.draw.rect(surface, (120, 70, 52), (620, 360, 260, 90))
    pygame.draw.rect(surface, (140, 84, 62), (640, 380, 60, 70))
    pygame.draw.rect(surface, (140, 84, 62), (800, 380, 60, 70))
    # standing lamp
    pygame.draw.line(surface, dark, (1120, 300), (1120, 480), 6)
    pygame.draw.polygon(surface, (200, 170, 100),
                        [(1080, 300), (1160, 300), (1140, 260), (1100, 260)])


_PROPS = {
    "gym": _paint_gym,
    "shelves": _paint_shelves,
    "plaza": _paint_plaza,
    "plaza_palma": _paint_plaza_palma,
    "fastfood": _paint_fastfood,
    "airport": _paint_airport,
    "living_room": _paint_living_room,
}
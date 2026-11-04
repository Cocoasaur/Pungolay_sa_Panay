"""Main menu background: a rustic industrial boxing gym, painted once.

Composition (following the reference description):
  - dark charcoal outer frame around the whole window
  - warm dark-brown wall with warehouse panels and a roof beam structure
  - hanging industrial lamps with warm glow
  - ventilation fans
  - wooden plank floor in the lower third
  - vignette so the interface stays the focus
"""

from __future__ import annotations

import math
import os

import pygame

import config

C = config.COLORS
W, H = config.BASE_WIDTH, config.BASE_HEIGHT


def build_menu_background() -> pygame.Surface:
    """Paint the full main-menu environment (with charcoal frame)."""
    if os.path.isfile(config.MENU_BACKGROUND_PATH):
        image = pygame.image.load(config.MENU_BACKGROUND_PATH).convert()
        if image.get_size() != (W, H):
            image = pygame.transform.smoothscale(image, (W, H))
        return image

    surface = pygame.Surface((W, H))

    # ---- charcoal outer frame ----------------------------------------
    frame_w = 16
    surface.fill(C["charcoal_dark"])
    inner = pygame.Rect(frame_w, frame_w, W - 2 * frame_w, H - 2 * frame_w)

    # ---- wall gradient ------------------------------------------------
    wall = pygame.Surface((inner.width, inner.height))
    top, bottom = (26, 19, 14), (52, 38, 26)
    for y in range(inner.height):
        t = y / max(1, inner.height - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(wall, color, (0, y), (inner.width, y))
    surface.blit(wall, inner.topleft)

    # ---- roof beam structure ------------------------------------------
    beam = (30, 24, 18)
    pygame.draw.rect(surface, beam, (inner.x, inner.y, inner.width, 74))
    pygame.draw.rect(surface, (42, 34, 26), (inner.x, inner.y, inner.width, 74), 2)
    for x in range(inner.x + 40, inner.right, 160):
        pygame.draw.line(surface, (24, 19, 14), (x, inner.y + 74),
                         (x + 110, inner.y + 18), 6)
        pygame.draw.line(surface, (24, 19, 14), (x + 160, inner.y + 74),
                         (x + 50, inner.y + 18), 6)

    # ---- warehouse wall panels ----------------------------------------
    for x in range(inner.x + 90, inner.right, 90):
        pygame.draw.line(surface, (22, 16, 12), (x, inner.y + 74),
                         (x, inner.y + 500), 2)
    wainscot = (44, 32, 22)
    pygame.draw.rect(surface, wainscot,
                     (inner.x, inner.y + 460, inner.width, 40))
    pygame.draw.line(surface, (24, 18, 13), (inner.x, inner.y + 460),
                     (inner.right, inner.y + 460), 3)

    # ---- ventilation fans ---------------------------------------------
    for fx, fy in (inner.x + 120, inner.y + 210), (inner.right - 120, inner.y + 250):
        pygame.draw.circle(surface, (24, 20, 16), (fx, fy), 26)
        pygame.draw.circle(surface, (52, 44, 36), (fx, fy), 26, 2)
        for i in range(4):
            ang = math.pi / 2 * i
            start = (fx + math.cos(ang) * 8, fy + math.sin(ang) * 8)
            end = (fx + math.cos(ang) * 22, fy + math.sin(ang) * 22)
            pygame.draw.line(surface, (58, 48, 38), start, end, 5)
        pygame.draw.circle(surface, (66, 54, 42), (fx, fy), 6)

    # ---- wooden floor --------------------------------------------------
    floor_top = inner.y + 500
    for y in range(floor_top, inner.bottom):
        t = (y - floor_top) / max(1, inner.bottom - floor_top)
        color = tuple(int(46 + (74 - 46) * t + 0.0) for _ in range(3))
        pygame.draw.line(surface, (int(46 + 26 * t), int(33 + 18 * t),
                                   int(22 + 12 * t)), (inner.x, y),
                         (inner.right, y))
    for y in range(floor_top + 14, inner.bottom, 14):
        pygame.draw.line(surface, (30, 22, 15), (inner.x, y), (inner.right, y), 2)
    for x in range(inner.x + 110, inner.right, 110):
        pygame.draw.line(surface, (30, 22, 15), (x, floor_top), (x, inner.bottom), 2)

    # ---- hanging lamps -------------------------------------------------
    for lx in (inner.x + 300, inner.x + W // 2, inner.right - 300):
        cable = (20, 16, 12)
        pygame.draw.line(surface, cable, (lx, inner.y + 18), (lx, inner.y + 118), 3)
        pygame.draw.polygon(surface, (52, 42, 32),
                            [(lx - 18, inner.y + 118), (lx + 18, inner.y + 118),
                             (lx + 12, inner.y + 148), (lx - 12, inner.y + 148)])
        # warm glow
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        for r in range(60, 0, -3):
            alpha = int(14 * (1 - r / 60))
            pygame.draw.circle(glow, C["warm_glow"] + (alpha,), (60, 60), r)
        surface.blit(glow, (lx - 60, inner.y + 92))
        pygame.draw.circle(surface, (255, 210, 140), (lx, inner.y + 148), 6)

    # ---- vignette ------------------------------------------------------
    vignette = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(120):
        alpha = int(22 * (1 - i / 120))
        pygame.draw.rect(vignette, (0, 0, 0, alpha),
                         (i, i, W - 2 * i, H - 2 * i), 2)
    surface.blit(vignette, (0, 0))

    # ---- inner frame border line --------------------------------------
    pygame.draw.rect(surface, C["border"], inner, 1)
    return surface
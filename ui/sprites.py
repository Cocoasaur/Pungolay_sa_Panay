"""PNG fighter sprites with procedural fallbacks.

Fighters are drawn with simple shapes in the visual language of the game:
white/light bodies, black outlines, red gloves, exaggerated limbs. One
function draws any fighter (player or enemy) based on its state machine.

Geometry is defined relative to the feet position, scaled by the distance-
based scale factor, and mirrored with `facing` (1 = right, -1 = left).
"""

from __future__ import annotations

import math
import os
from functools import lru_cache

import pygame

import config
from ui.animation import draw_animation

C = config.COLORS


@lru_cache(maxsize=32)
def _load_sprite(path: str) -> pygame.Surface:
    image = pygame.image.load(path).convert_alpha()
    bounds = image.get_bounding_rect()
    # Size the visible character, keeping transparent borders out of the
    # height calculation and the feet anchored at the ground position.
    if bounds.width and bounds.height:
        return image.subsurface(bounds).copy()
    return image


@lru_cache(maxsize=128)
def _scaled_sprite(path: str, width: int, height: int,
                   facing: int) -> pygame.Surface:
    image = pygame.transform.smoothscale(_load_sprite(path), (width, height))
    if facing < 0:
        image = pygame.transform.flip(image, True, False)
    return image


def _sprite_path(fighter_id: str, state: str) -> str | None:
    if fighter_id != "player" and fighter_id not in config.ENEMIES:
        raise ValueError(f"Unknown fighter sprite id: {fighter_id}")

    sprite_names = [fighter_id]
    if fighter_id in config.ENEMIES:
        sprite_names.append("enemy")

    for name in sprite_names:
        state_path = os.path.join(config.SPRITES_DIR, f"{name}_{state}.png")
        if os.path.isfile(state_path):
            return state_path

    for name in sprite_names:
        default_path = os.path.join(config.SPRITES_DIR, f"{name}.png")
        if os.path.isfile(default_path):
            return default_path
    return None


def _limb(surface, a, b, width, color, outline):
    """A limb as a thick outlined line (simple but readable)."""
    pygame.draw.line(surface, outline, a, b, int(width + 3))
    pygame.draw.line(surface, color, a, b, int(width))


def draw_boxer(surface, x: float, foot_y: float, facing: int, state: str,
               anim_t: float, scale: float, trunks_color: tuple,
               flash: bool = False, hit_lean: float = 0.0,
               fighter_id: str = "player", action_time: float | None = None,
               charged: bool = False, punch_side: str = "right", motion_direction: int = 0) -> None:
    """Draw one fighter at ground position x with feet on foot_y."""
    s = scale * config.FIGHTER_SIZE
    cx = x
    outline = C["fighter_outline"]
    white = C["fighter_white"]

    # --- shadow ---------------------------------------------------------
    shadow = pygame.Surface((int(70 * s), int(16 * s)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
    surface.blit(shadow, (int(cx - 35 * s), int(foot_y - 10 * s)))

    if draw_animation(surface, fighter_id, state,
                      anim_t if action_time is None else action_time, cx, foot_y,
                      scale, facing, flash, charged, punch_side, motion_direction):
        return
    sprite_path = _sprite_path(fighter_id, state)
    if sprite_path is not None:
        sprite_height = max(1, int(config.FIGHTER_BODY_HEIGHT * scale))
        source = _load_sprite(sprite_path)
        sprite_width = max(
            1, int(sprite_height * source.get_width() / source.get_height()))
        sprite = _scaled_sprite(sprite_path, sprite_width, sprite_height,
                                facing)
        if flash:
            sprite = sprite.copy()
            # Brighten only the character, keeping transparent padding clear.
            sprite.fill((90, 90, 90, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(sprite, (int(cx - sprite_width / 2),
                              int(foot_y - sprite_height)))
        return

    if state in ("knockdown", "ko"):
        _draw_lying(surface, cx, foot_y, facing, s, outline, white,
                    trunks_color, anim_t)
        return

    # --- body layout ----------------------------------------------------
    bob = math.sin(anim_t * 3.2) * 2.0 * s if state in ("idle", "walk") else 0.0
    if state == "walk":
        bob *= 1.8
    lean = hit_lean * s * facing      # knock the fighter backward when hit
    bx = cx - lean

    head_r = 13 * s
    head_cy = foot_y - 106 * s + bob
    head_cx = bx + 3 * s * facing

    shoulder_y = foot_y - 86 * s + bob
    hip_y = foot_y - 40 * s
    torso_w = 30 * s
    hip_w = 20 * s

    # --- legs -----------------------------------------------------------
    leg_color = (52, 48, 44)
    step = 0.0
    if state in ("walk", "retreat"):
        step = math.sin(anim_t * 7.0) * 7 * s
    _limb(surface, (bx - 7 * s, hip_y), (bx - 9 * s - step, foot_y - 3 * s),
          7 * s, leg_color, outline)
    _limb(surface, (bx + 7 * s, hip_y), (bx + 9 * s + step, foot_y - 3 * s),
          7 * s, leg_color, outline)
    for fx in (bx - 10 * s - step, bx + 10 * s + step):
        pygame.draw.ellipse(surface, (30, 28, 26),
                            (fx - 6 * s, foot_y - 5 * s, 12 * s, 6 * s))

    # --- torso ----------------------------------------------------------
    pygame.draw.polygon(surface, white, [
        (bx - torso_w / 2, shoulder_y),
        (bx + torso_w / 2, shoulder_y),
        (bx + hip_w / 2, hip_y),
        (bx - hip_w / 2, hip_y),
    ])
    pygame.draw.polygon(surface, outline, [
        (bx - torso_w / 2, shoulder_y),
        (bx + torso_w / 2, shoulder_y),
        (bx + hip_w / 2, hip_y),
        (bx - hip_w / 2, hip_y),
    ], 2)
    pygame.draw.circle(surface, white, (int(bx), int(shoulder_y)), int(torso_w / 2))
    pygame.draw.circle(surface, outline, (int(bx), int(shoulder_y)),
                       int(torso_w / 2), 2)

    # --- trunks ---------------------------------------------------------
    pygame.draw.rect(surface, trunks_color,
                     (bx - hip_w / 2, hip_y, hip_w, 10 * s))
    pygame.draw.rect(surface, outline, (bx - hip_w / 2, hip_y, hip_w, 10 * s), 2)
    pygame.draw.line(surface, (24, 22, 20), (bx - hip_w / 2, hip_y),
                     (bx + hip_w / 2, hip_y), 2)

    # --- arms & gloves --------------------------------------------------
    front_sx = bx + 13 * s * facing
    rear_sx = bx - 13 * s * facing
    punch = state.startswith("punch_")
    punch_side = state[6:] if punch else None   # "l" or "r"
    guard = state == "guard"
    hit = state == "hit"

    if punch and punch_side == "r":
        _draw_arm(surface, (front_sx, shoulder_y), facing, s, "extend",
                  outline, white, anim_t, punch=True)
        _draw_arm(surface, (rear_sx, shoulder_y), facing, s, "guard_up",
                  outline, white, anim_t)
    elif punch and punch_side == "l":
        _draw_arm(surface, (rear_sx, shoulder_y), facing, s, "extend",
                  outline, white, anim_t, punch=True)
        _draw_arm(surface, (front_sx, shoulder_y), facing, s, "guard_up",
                  outline, white, anim_t)
    elif guard:
        _draw_arm(surface, (front_sx, shoulder_y), facing, s, "guard_up",
                  outline, white, anim_t)
        _draw_arm(surface, (rear_sx, shoulder_y), facing, s, "guard_up",
                  outline, white, anim_t)
    elif hit:
        _draw_arm(surface, (front_sx, shoulder_y), facing, s, "flail",
                  outline, white, anim_t)
        _draw_arm(surface, (rear_sx, shoulder_y), facing, s, "guard_low",
                  outline, white, anim_t)
    else:
        _draw_arm(surface, (front_sx, shoulder_y), facing, s, "idle",
                  outline, white, anim_t)
        _draw_arm(surface, (rear_sx, shoulder_y), facing, s, "idle",
                  outline, white, anim_t)

    # --- head -----------------------------------------------------------
    pygame.draw.circle(surface, white, (int(head_cx), int(head_cy)),
                       int(head_r))
    pygame.draw.circle(surface, outline, (int(head_cx), int(head_cy)),
                       int(head_r), 2)
    # hair line, subtle
    pygame.draw.arc(surface, (150, 145, 140),
                    (head_cx - head_r, head_cy - head_r, 2 * head_r, 2 * head_r),
                    math.pi * 0.9, math.pi * 1.9, 2)

    # hit flash: translucent white overlay over the whole body
    if flash:
        overlay = pygame.Surface((int(80 * s), int(120 * s)), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 90))
        surface.blit(overlay, (int(cx - 40 * s), int(foot_y - 118 * s)))


def _draw_arm(surface, shoulder, facing, s, mode: str, outline, white,
              anim_t, punch: bool = False) -> None:
    """One arm from `shoulder` with a pose chosen by `mode`."""
    sx, sy = shoulder
    if mode == "extend":
        # fully extended toward the opponent
        wrist = (sx + facing * 34 * s, sy + 4 * s)
        elbow = (sx + facing * 18 * s, sy + 6 * s)
    elif mode == "guard_up":
        # fist up near the face
        wrist = (sx + facing * 16 * s, sy - 16 * s)
        elbow = (sx + facing * 8 * s, sy - 2 * s)
    elif mode == "flail":
        t = math.sin(anim_t * 24) * 4 * s
        wrist = (sx - facing * 14 * s, sy - 26 * s + t)
        elbow = (sx - facing * 6 * s, sy - 12 * s)
    elif mode == "guard_low":
        wrist = (sx - facing * 10 * s, sy + 16 * s)
        elbow = (sx - facing * 4 * s, sy + 8 * s)
    else:  # idle: relaxed guard
        sway = math.sin(anim_t * 3.2) * 2 * s
        wrist = (sx + facing * 10 * s, sy + 14 * s + sway)
        elbow = (sx + facing * 5 * s, sy + 6 * s)

    _limb(surface, shoulder, elbow, 7 * s, white, outline)
    _limb(surface, elbow, wrist, 6 * s, white, outline)
    glove_r = 8 * s
    pygame.draw.circle(surface, C["glove_red"], (int(wrist[0]), int(wrist[1])),
                       int(glove_r))
    pygame.draw.circle(surface, C["glove_red_dark"],
                       (int(wrist[0]), int(wrist[1])), int(glove_r), 2)


def _draw_lying(surface, cx, foot_y, facing, s, outline, white,
                trunks_color, anim_t) -> None:
    """Fighter flat on the canvas, facing up, one glove raised in defeat."""
    body_y = foot_y - 8 * s
    head_x = cx - facing * 18 * s
    # torso lying horizontally
    pygame.draw.ellipse(surface, white,
                        (cx - facing * 30 * s - 16 * s, body_y - 8 * s,
                         34 * s, 16 * s))
    pygame.draw.ellipse(surface, outline,
                        (cx - facing * 30 * s - 16 * s, body_y - 8 * s,
                         34 * s, 16 * s), 2)
    pygame.draw.rect(surface, trunks_color,
                     (cx - facing * 26 * s, body_y - 8 * s, 20 * s, 12 * s))
    # legs
    _limb(surface, (cx - facing * 6 * s, body_y - 2 * s),
          (cx + facing * 26 * s, body_y - 2 * s), 6 * s, (52, 48, 44), outline)
    # head
    pygame.draw.circle(surface, white, (int(head_x), int(body_y - 4 * s)),
                       int(11 * s))
    pygame.draw.circle(surface, outline, (int(head_x), int(body_y - 4 * s)),
                       int(11 * s), 2)
    # one glove raised weakly (defeat pose)
    wrist = (head_x - facing * 14 * s, body_y - 24 * s)
    _limb(surface, (head_x - facing * 6 * s, body_y - 8 * s), wrist,
          5 * s, white, outline)
    pygame.draw.circle(surface, C["glove_red"], (int(wrist[0]), int(wrist[1])),
                       int(7 * s))

"""Manifest-driven clips with authored frame bounds and grounded foot pivots."""

from functools import lru_cache
import json
from pathlib import Path
import pygame
import config
from ui.assets import load_image


@lru_cache(maxsize=4)
def manifest(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=128)
def frame_image(path, rect, width, height, facing):
    sheet = load_image(path)
    if sheet is None:
        return None
    frame = sheet.subsurface(pygame.Rect(rect))
    image = pygame.transform.smoothscale(frame, (width, height))
    return pygame.transform.flip(image, True, False) if facing < 0 else image


def draw_animation(
    surface,
    fighter_id,
    state,
    t,
    x,
    foot_y,
    scale,
    facing,
    flash=False,
    charged=False,
    side="right",
    direction=0,
):
    data = manifest(str(Path(config.SPRITES_DIR) / "animations.json"))
    fighter = data.get("fighters", {}).get(fighter_id)
    if not fighter:
        return False
    forced = None
    if state.startswith("punch_"):
        action = ("haymaker_" if charged else "punch_") + state[-1]
        forced = (
            0
            if t < config.PLAYER["punch_active_start"]
            else 1 if t <= config.PLAYER["punch_active_end"] else 2
        )
    elif state in ("windup", "attack", "recover"):
        action = ("haymaker_" if charged else "punch_") + ("l" if side == "left" else "r")
        forced = {"windup": 0, "attack": 1, "recover": 2}[state]
    elif state in ("guard", "defend"):
        action = "guard"
    elif state in ("walk", "approach", "retreat"):
        action = "walk"
    elif state == "charging":
        action = "haymaker_l"
        forced = 0
    else:
        return False
    clip = fighter.get("clips", {}).get(action)
    if not clip:
        return False
    frames = clip["frames"]
    durations = clip["durations"]
    if forced is not None:
        index = forced
    elif action == "guard":
        index = 0 if t < durations[0] else 1
    else:
        elapsed = max(0, t) % sum(durations) if action == "walk" else max(0, t)
        index = len(frames) - 1
        for i, duration in enumerate(durations):
            if elapsed < duration:
                index = i
                break
            elapsed -= duration
    if action == "walk" and (state == "retreat" or (direction and direction != facing)):
        index = len(frames) - 1 - index
    item = frames[min(index, len(frames) - 1)]
    rect = tuple(item["rect"])
    reference = fighter["reference_height"] * rect[3]
    factor = config.FIGHTER_BODY_HEIGHT * scale / reference
    width = max(1, round(rect[2] * factor))
    height = max(1, round(rect[3] * factor))
    image = frame_image(str(Path(config.SPRITES_DIR) / clip["sheet"]), rect, width, height, facing)
    if image is None:
        return False
    px, py = item["pivot"]
    px = px * width if facing > 0 else (1 - px) * width
    if flash:
        image = image.copy()
        image.fill((90, 90, 90, 0), special_flags=pygame.BLEND_RGBA_ADD)
    surface.blit(image, (round(x - px), round(foot_y - py * height)))
    return True

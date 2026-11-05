"""One display projection for all camera views; inference stays unmirrored."""

import cv2
import pygame
import config


def preview_key(game):
    return (
        game.tracking.sample_id,
        game.raw_landmarks,
        bool(game.settings.get("mirror_input", True)),
        game.gestures.line_reach,
        bool(game.last_pose and game.last_pose.present),
        id(game.last_camera_frame),
    )


def render_preview(game, frame, pose):
    mirror = bool(game.settings.get("mirror_input", True))
    if pose is None:
        out = cv2.flip(frame, 1) if mirror else frame.copy()
    else:
        out = game.pose_tracker.draw_debug_frame(frame, pose, raw=game.raw_landmarks, mirror=mirror)
        out = game.gestures.draw_punch_boundary(out, pose, game.calibrator.existing, mirror=mirror)
    h, w = out.shape[:2]
    for fraction in (config.CAMERA_MOVEMENT_LEFT, 0.5, config.CAMERA_MOVEMENT_RIGHT):
        x = round(fraction * (w - 1))
        color = (165, 165, 165) if fraction != 0.5 else (211, 231, 242)
        for y in range(30, h - 22, 16):
            cv2.line(out, (x, y), (x, min(y + 6, h - 22)), color, 1)
    return out


def label_guides(surface, fonts):
    """Label after scaling so the small gameplay inset remains readable."""
    from ui.fonts import cached_text

    width, height = surface.get_size()
    for fraction, label in (
        (config.CAMERA_MOVEMENT_LEFT, "L"),
        (0.5, "C" if width <= 320 else "CENTER"),
        (config.CAMERA_MOVEMENT_RIGHT, "R"),
    ):
        image = cached_text(fonts["tiny"], label, (242, 231, 211))
        rect = image.get_rect(midbottom=(round(fraction * (width - 1)), height - 2))
        pygame.draw.rect(surface, (23, 21, 18), rect.inflate(4, 2))
        surface.blit(image, rect)

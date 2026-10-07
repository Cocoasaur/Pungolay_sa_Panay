"""Relative distance estimation.

Compares the current detected body scale against the calibration reference:

    ratio = reference_size / detected_size

ratio > 1 means the player is closer than during calibration, ratio < 1 means
further. That ratio drives both the FAR/MEDIUM/CLOSE classification and the
fighter sprite scale. This is deliberately a *relative* estimate -- without
true camera intrinsics we never claim to know distances in centimeters.
"""

from __future__ import annotations

from typing import Optional

import config


class DistanceEstimator:
    def __init__(self, calibration, sensitivity: float = 1.0) -> None:
        self._calibration = calibration
        self._sensitivity = sensitivity
        self._smoothed = 1.0

    def set_calibration(self, calibration) -> bool:
        """Apply calibration and report whether its measurements changed.

        Settings are applied frequently (including when Settings is closed).
        Keeping the filtered ratio in that case prevents a visible depth jump.
        """
        changed = not self._same_calibration(self._calibration, calibration)
        self._calibration = calibration
        if changed:
            self._smoothed = 1.0
        return changed

    @staticmethod
    def _same_calibration(left, right) -> bool:
        return (
            abs(left.shoulder_width - right.shoulder_width) < 1e-6 and
            abs(left.torso_height - right.torso_height) < 1e-6 and
            abs(left.neutral_x - right.neutral_x) < 1e-6
        )

    def set_sensitivity(self, value: float) -> None:
        self._sensitivity = max(0.2, min(3.0, value))

    def update(self, pose, dt: float, torso_only: bool = False,
               freeze: bool = False) -> tuple:
        """Return (ratio, level, sprite_scale); freeze keeps the previous filter."""
        target = 1.0
        if pose.present:
            ratios = []
            weights = []
            if not torso_only and pose.shoulder_width > 0.03:
                ratios.append(self._calibration.shoulder_width / pose.shoulder_width)
                weights.append(0.35)
            if pose.torso_height > 0.05:
                ratios.append(self._calibration.torso_height / pose.torso_height)
                weights.append(0.65)
            if ratios:
                target = sum(ratio * weight for ratio, weight in zip(ratios, weights)) / sum(weights)
            # sensitivity>1 exaggerates movement; <1 damps it
                target = 1.0 + (target - 1.0) * self._sensitivity

        if not freeze:
            alpha = 1.0 - config.DISTANCE_SMOOTHING ** (dt * 60.0)
            self._smoothed += (target - self._smoothed) * alpha
        ratio = max(0.3, min(3.0, self._smoothed))

        if ratio >= config.DISTANCE_CLOSE_RATIO:
            level = "CLOSE"
        elif ratio <= config.DISTANCE_FAR_RATIO:
            level = "FAR"
        else:
            level = "MEDIUM"

        # sprite scale: grow when close, shrink when far
        scale = config.DISTANCE_SCALE_MIN + (ratio - config.DISTANCE_FAR_RATIO) * (
            (config.DISTANCE_SCALE_MAX - config.DISTANCE_SCALE_MIN)
            / (config.DISTANCE_CLOSE_RATIO - config.DISTANCE_FAR_RATIO))
        scale = max(config.DISTANCE_SCALE_MIN, min(config.DISTANCE_SCALE_MAX, scale))
        return ratio, level, scale

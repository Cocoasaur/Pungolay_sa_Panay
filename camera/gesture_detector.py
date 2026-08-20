"""Gesture detection from pose landmarks: punches and guard.

PUNCH: the wrist must (a) move rapidly toward the camera (z velocity beyond
a threshold), (b) be clearly in front of the shoulder plane, and (c) have the
arm at least partially extended. A short per-hand cooldown prevents machine-
gun punching. Thresholds are scaled by the punch-sensitivity setting.

GUARD: both wrists must stay within a radius of the nose for a short hold
time -- hands up near the face, the classic boxing guard.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Tuple

import config
from camera.pose_tracker import (LM_LEFT_ELBOW, LM_LEFT_SHOULDER, LM_LEFT_WRIST,
                                 LM_NOSE, LM_RIGHT_ELBOW, LM_RIGHT_SHOULDER,
                                 LM_RIGHT_WRIST, PoseData)

_HISTORY_LEN = 8


class GestureDetector:
    def __init__(self, punch_sensitivity: float = 1.0) -> None:
        self._left_history: Deque[Tuple[float, float, float, float]] = deque()
        self._right_history: Deque[Tuple[float, float, float, float]] = deque()
        self._left_cooldown_until = 0.0
        self._right_cooldown_until = 0.0
        self._guard_hold = 0.0
        self.guard = False
        self._hands_up_hold = 0.0   # for the knockdown get-up gesture
        self.left_punch = False
        self.right_punch = False
        self.hands_up = False
        self.punch_sensitivity = punch_sensitivity

    def set_punch_sensitivity(self, value: float) -> None:
        self.punch_sensitivity = max(0.5, min(3.0, value))

    # ------------------------------------------------------------------
    def update(self, pose: PoseData, dt: float, now: float | None = None) -> None:
        """Feeds one pose frame. Fills self.left_punch / right_punch / guard."""
        self.left_punch = False
        self.right_punch = False
        if now is None:
            now = time.monotonic()

        if not pose.present:
            self._left_history.clear()
            self._right_history.clear()
            self._guard_hold = 0.0
            self._hands_up_hold = 0.0
            self.guard = False
            return

        nose = pose.lm(LM_NOSE)
        lw = pose.lm(LM_LEFT_WRIST)
        rw = pose.lm(LM_RIGHT_WRIST)

        # -- punches -----------------------------------------------------
        left = self._detect_punch("left", pose, self._left_history,
                                  now, dt, sensitivity=self.punch_sensitivity)
        right = self._detect_punch("right", pose, self._right_history,
                                   now, dt, sensitivity=self.punch_sensitivity)
        self.left_punch = left
        self.right_punch = right

        # -- guard -------------------------------------------------------
        guard_now = False
        if (nose is not None and lw is not None and rw is not None and
                lw[3] > config.POSE_MIN_LANDMARK_VIS and
                rw[3] > config.POSE_MIN_LANDMARK_VIS):
            d_l = _distance2d(lw, nose)
            d_r = _distance2d(rw, nose)
            if d_l < config.GUARD_WRIST_NOSE_DIST and d_r < config.GUARD_WRIST_NOSE_DIST:
                guard_now = True
        if guard_now:
            self._guard_hold += dt
        else:
            self._guard_hold = 0.0
        self.guard = self._guard_hold >= config.GUARD_HOLD_TIME

        # -- get-up gesture (both hands raised high) ---------------------
        ls = pose.lm(LM_LEFT_SHOULDER)
        rs = pose.lm(LM_RIGHT_SHOULDER)
        hands_up = False
        if lw and rw and ls and rs:
            shoulder_y = (ls[1] + rs[1]) / 2
            if (lw[1] < shoulder_y - 0.15 and rw[1] < shoulder_y - 0.15 and
                    lw[3] > config.POSE_MIN_LANDMARK_VIS and
                    rw[3] > config.POSE_MIN_LANDMARK_VIS):
                hands_up = True
        if hands_up:
            self._hands_up_hold += dt
        else:
            self._hands_up_hold = 0.0
        self.hands_up = self._hands_up_hold >= config.GETUP_HANDS_UP_TIME

    # ------------------------------------------------------------------
    def _detect_punch(self, side: str, pose: PoseData, history,
                      now: float, dt: float, sensitivity: float) -> bool:
        wrist_idx = LM_LEFT_WRIST if side == "left" else LM_RIGHT_WRIST
        elbow_idx = LM_LEFT_ELBOW if side == "left" else LM_RIGHT_ELBOW
        shoulder_idx = LM_LEFT_SHOULDER if side == "left" else LM_RIGHT_SHOULDER

        cooldown_until = self._left_cooldown_until if side == "left" else self._right_cooldown_until
        if now < cooldown_until:
            self._push(history, None)
            return False

        wrist = pose.lm(wrist_idx)
        elbow = pose.lm(elbow_idx)
        shoulder = pose.lm(shoulder_idx)
        self._push(history, wrist)

        if wrist is None or elbow is None or shoulder is None:
            return False
        if wrist[3] < config.POSE_MIN_LANDMARK_VIS or elbow[3] < config.POSE_MIN_LANDMARK_VIS:
            return False

        if pose.is_2d:
            return self._detect_punch_2d(side, pose, wrist, elbow, shoulder,
                                         history, dt, sensitivity)

        # z is depth: mediapipe reports negative z toward the camera.
        # A punch = wrist moving fast *toward* the camera, past the shoulder
        # plane, with the arm at least partly extended.
        z_velocity = (wrist[2] - history[0][2]) / max(dt, 1e-3) if history[0] else 0.0
        z_forward = shoulder[2] - wrist[2]
        arm_extended = _distance2d(elbow, wrist)

        threshold_velocity = -config.PUNCH_Z_VELOCITY / sensitivity
        threshold_forward = config.PUNCH_Z_FORWARD / sensitivity

        if (z_velocity < threshold_velocity and
                z_forward > threshold_forward and
                arm_extended > config.PUNCH_ARM_EXTENDED):
            self._set_cooldown(side, now)
            return True
        return False

    def _detect_punch_2d(self, side: str, pose: PoseData, wrist, elbow,
                         shoulder, history, dt: float, sensitivity: float) -> bool:
        """Punch without depth: the arm must extend sharply and the wrist
        must move quickly across the body (both relative to shoulder width)."""
        rs = pose.lm(LM_RIGHT_SHOULDER)
        ls = pose.lm(LM_LEFT_SHOULDER)
        if rs is None or ls is None:
            return False
        sw = abs(rs[0] - ls[0])
        if sw < 1e-4:
            return False

        extension = _distance2d(wrist, shoulder) / sw
        if extension < config.PUNCH2D_EXT_MIN:
            return False

        # arm-extension speed over the short history window
        past = None
        for sample in history:
            if sample is not None:
                past = sample
                break
        if past is None:
            return False
        ext_speed = abs(extension - (_distance2d(past, shoulder) / sw)) / max(dt, 1e-3)

        # lateral wrist speed: how fast the fist crosses the body
        wrist_speed = abs(wrist[0] - past[0]) / max(dt, 1e-3) / sw

        threshold_speed = config.PUNCH2D_EXT_SPEED / sensitivity
        if (ext_speed > threshold_speed and
                wrist_speed > config.PUNCH2D_WRIST_SPEED / sensitivity):
            self._set_cooldown(side, time.monotonic())
            return True
        return False

    def _set_cooldown(self, side: str, now: float) -> None:
        if side == "left":
            self._left_cooldown_until = now + config.PUNCH_COOLDOWN
        else:
            self._right_cooldown_until = now + config.PUNCH_COOLDOWN

    def _push(self, history, value) -> None:
        history.append(value)
        while len(history) > _HISTORY_LEN:
            history.popleft()


def _distance2d(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
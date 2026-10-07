"""Gesture detection from pose landmarks: punches, guard, and Haymaker charge.

Refactored to use explicit state machines per hand, hysteresis, and body-relative
coordinates for robust tracking.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

import config
from camera.pose_tracker import (LM_LEFT_ELBOW, LM_LEFT_HIP, LM_LEFT_SHOULDER, LM_LEFT_WRIST,
                                 LM_NOSE, LM_RIGHT_ELBOW, LM_RIGHT_SHOULDER,
                                 LM_RIGHT_HIP, LM_RIGHT_WRIST, PoseData)
from camera.punch_boundary import punch_boundary

_HISTORY_LEN = 8


class HandContext:
    def __init__(self, side: str):
        self.side = side
        self.state = "NEUTRAL" # NEUTRAL, CHARGING, CHARGED
        self.charge_time = 0.0
        self.history = deque(maxlen=_HISTORY_LEN)
        self.cooldown_until = 0.0
        self.punch_confirm_hold = 0.0
        self.line_armed = False
        self.pending_haymaker = False
        
        # outputs
        self.punch_now = False
        self.haymaker_now = False


class GestureDetector:
    def __init__(self, punch_sensitivity: float = 1.0) -> None:
        self.left_hand = HandContext("left")
        self.right_hand = HandContext("right")
        self._guard_hold = 0.0
        self.guard = False
        self._hands_up_hold = 0.0
        self.hands_up = False
        
        # outputs
        self.left_punch = False
        self.right_punch = False
        self.left_haymaker = False
        self.right_haymaker = False
        self.charge_progress = 0.0
        self.is_charging = False
        self.is_charged = False
        self._line_torso_height = None

        self.punch_sensitivity = punch_sensitivity

    def set_punch_sensitivity(self, value: float) -> None:
        self.punch_sensitivity = max(0.5, min(3.0, value))

    def update(self, pose: PoseData, dt: float, calibration: Any = None, now: float | None = None) -> None:
        if now is None:
            now = time.monotonic()
            
        self.left_punch = False
        self.right_punch = False
        self.left_haymaker = False
        self.right_haymaker = False
        self.is_charging = False
        self.is_charged = False
        self.charge_progress = 0.0
        
        if not pose.present:
            self.left_hand = HandContext("left")
            self.right_hand = HandContext("right")
            self._guard_hold = 0.0
            self._hands_up_hold = 0.0
            self.guard = False
            self.hands_up = False
            return

        nose = pose.lm(LM_NOSE)
        lw = pose.lm(LM_LEFT_WRIST)
        rw = pose.lm(LM_RIGHT_WRIST)
        ls = pose.lm(LM_LEFT_SHOULDER)
        rs = pose.lm(LM_RIGHT_SHOULDER)
        
        sw = 0.1
        if ls and rs:
            sw = abs(ls[0] - rs[0]) + 0.001
        # -- GUARD --
        ref_len = calibration.arm_length if (calibration and hasattr(calibration, "arm_length")) else sw
        guard_now = False
        if nose and lw and rw and ls and rs:
            d_l = _distance2d(lw, nose) / ref_len
            d_r = _distance2d(rw, nose) / ref_len
            
            threshold = config.BLOCK_EXIT_THRESHOLD if self.guard else config.BLOCK_ENTER_THRESHOLD
            
            if d_l < threshold and d_r < threshold:
                guard_now = True
                
        if guard_now:
            self._guard_hold += dt
        else:
            self._guard_hold = 0.0
            
        self.guard = self._guard_hold >= config.GUARD_HOLD_TIME

        # -- HANDS --
        self._process_hand(self.left_hand, pose, dt, now, sw, calibration)
        self._process_hand(self.right_hand, pose, dt, now, sw, calibration)
        
        self.left_punch = self.left_hand.punch_now
        self.right_punch = self.right_hand.punch_now
        self.left_haymaker = self.left_hand.haymaker_now
        self.right_haymaker = self.right_hand.haymaker_now
        
        # Charge UI logic
        lh_state = self.left_hand.state
        rh_state = self.right_hand.state
        if lh_state in ("CHARGING", "CHARGED"):
            self.is_charging = True
            self.charge_progress = self.left_hand.charge_time / config.HAYMAKER_CHARGE_TIME
            if lh_state == "CHARGED":
                self.is_charged = True
        elif rh_state in ("CHARGING", "CHARGED"):
            self.is_charging = True
            self.charge_progress = self.right_hand.charge_time / config.HAYMAKER_CHARGE_TIME
            if rh_state == "CHARGED":
                self.is_charged = True

        self.charge_progress = min(1.0, max(0.0, self.charge_progress))

        # -- GET UP --
        hands_up = False
        if lw and rw and ls and rs:
            shoulder_y = (ls[1] + rs[1]) / 2
            if lw[1] < shoulder_y - 0.15 and rw[1] < shoulder_y - 0.15:
                hands_up = True
        if hands_up:
            self._hands_up_hold += dt
        else:
            self._hands_up_hold = 0.0
        self.hands_up = self._hands_up_hold >= config.GETUP_HANDS_UP_TIME

    def _process_hand(self, ctx: HandContext, pose: PoseData, dt: float, now: float, sw: float, calibration: Any):
        ctx.punch_now = False
        ctx.haymaker_now = False
        
        wrist_idx = LM_LEFT_WRIST if ctx.side == "left" else LM_RIGHT_WRIST
        elbow_idx = LM_LEFT_ELBOW if ctx.side == "left" else LM_RIGHT_ELBOW
        shoulder_idx = LM_LEFT_SHOULDER if ctx.side == "left" else LM_RIGHT_SHOULDER
        
        wrist = pose.lm(wrist_idx)
        elbow = pose.lm(elbow_idx)
        shoulder = pose.lm(shoulder_idx)
        
        landmarks = (wrist, elbow, shoulder)
        if (not all(landmarks) or
                min(lm[3] for lm in landmarks) < config.POSE_MIN_LANDMARK_VIS):
            ctx.history.clear()
            ctx.state = "NEUTRAL"
            ctx.charge_time = 0.0
            ctx.punch_confirm_hold = 0.0
            ctx.line_armed = False
            ctx.pending_haymaker = False
            return

        boundary = self.boundary_for(pose, calibration)
        ref_len = boundary.arm_length if boundary else max(0.05, sw)
        relative_wrist = tuple((wrist[i] - shoulder[i]) / ref_len for i in range(3))
        ctx.history.append((now, relative_wrist))
        
        if self.guard:
            ctx.state = "NEUTRAL"
            ctx.charge_time = 0.0
            ctx.punch_confirm_hold = 0.0
            ctx.pending_haymaker = False
            if boundary and boundary.reach(wrist) <= -config.PUNCH_LINE_REARM:
                ctx.line_armed = True
            return

        if pose.is_2d:
            is_punching = False
            if boundary is not None:
                reach = boundary.reach(wrist)
                if reach <= -config.PUNCH_LINE_REARM:
                    ctx.line_armed = True
                is_punching = (ctx.line_armed and reach >= 0.0 and
                               boundary.top <= wrist[1] <= boundary.bottom)
            else:
                ctx.line_armed = False
        else:
            is_punching = self._is_punching(ctx, wrist, elbow, shoulder, now, ref_len)
        if is_punching:
            if ctx.punch_confirm_hold == 0.0:
                ctx.pending_haymaker = ctx.state == "CHARGED"
            ctx.punch_confirm_hold += dt
            if ctx.punch_confirm_hold >= config.PUNCH_CONFIRMATION_TIME:
                if now >= ctx.cooldown_until:
                    ctx.cooldown_until = now + config.PUNCH_COOLDOWN
                    if ctx.pending_haymaker:
                        ctx.haymaker_now = True
                    else:
                        ctx.punch_now = True
                
                ctx.state = "NEUTRAL"
                ctx.charge_time = 0.0
                ctx.punch_confirm_hold = 0.0
                ctx.line_armed = False
                ctx.pending_haymaker = False
                return
        else:
            ctx.punch_confirm_hold = 0.0
            ctx.pending_haymaker = False
            
        # -- CHARGE DETECTION --
        arm_bend = _distance2d(wrist, shoulder) / ref_len
        is_tucked = arm_bend < config.CHARGE_MIN_BEND
        
        x_offset = (wrist[0] - shoulder[0]) / ref_len
        # If facing right, rear is -x. If facing left, rear is +x.
        facing_dir = boundary.direction if boundary else 1.0
        
        # relative offset: positive means forward, negative means backward
        rel_x_offset = x_offset * facing_dir
        
        thresh_enter = config.CHARGE_ENTER_THRESHOLD
        thresh_exit = config.CHARGE_EXIT_THRESHOLD
        
        if ctx.state == "NEUTRAL":
            if is_tucked and rel_x_offset < thresh_enter:
                ctx.state = "CHARGING"
                ctx.charge_time = dt
        elif ctx.state in ("CHARGING", "CHARGED"):
            if not is_tucked or rel_x_offset > thresh_exit:
                ctx.state = "NEUTRAL"
                ctx.charge_time = 0.0
            else:
                ctx.charge_time += dt
                if ctx.state == "CHARGING" and ctx.charge_time >= config.HAYMAKER_CHARGE_TIME:
                    ctx.state = "CHARGED"

    def _is_punching(self, ctx: HandContext, wrist, elbow, shoulder,
                     now: float, ref_len: float) -> bool:
        history = ctx.history
        if len(history) < 2:
            return False
            
        arm_extended = _distance2d(elbow, wrist) / ref_len
        
        past_time, past = history[0]
        relative_z = (wrist[2] - shoulder[2]) / ref_len
        z_velocity = (relative_z - past[2]) * ref_len / max(now - past_time, 1e-3)
        z_forward = shoulder[2] - wrist[2]
        
        threshold_velocity = -config.PUNCH_Z_VELOCITY / self.punch_sensitivity
        threshold_forward = config.PUNCH_Z_FORWARD / self.punch_sensitivity
        
        if (z_velocity < threshold_velocity and
                z_forward > threshold_forward and
                arm_extended > config.PUNCH_ARM_EXTENDED):
            return True
        return False

    def boundary_for(self, pose, calibration):
        """Keep the line's last reliable scale when hips leave the image."""
        if not pose.present:
            return None
        torso_points = [pose.lm(index) for index in (
            LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER, LM_LEFT_HIP, LM_RIGHT_HIP)]
        if (pose.torso_height > 0.05 and all(
                point is not None and point[3] >= config.POSE_MIN_LANDMARK_VIS
                for point in torso_points)):
            self._line_torso_height = pose.torso_height
        torso = self._line_torso_height
        if torso is None:
            torso = getattr(calibration, "torso_height", 0.36)
        return punch_boundary(pose, calibration, self.punch_sensitivity,
                              torso_height=torso)

    def draw_punch_boundary(self, frame, pose, calibration):
        """Show the same body-relative line used by the 2D punch detector."""
        if pose is None or not pose.is_2d:
            return frame
        boundary = self.boundary_for(pose, calibration)
        if boundary is None:
            return frame
        import cv2
        out = frame.copy()
        height, width = out.shape[:2]
        x = int(boundary.x * width)
        if not 0 <= x < width:
            return out
        top = max(0, min(height - 1, int(boundary.top * height)))
        bottom = max(0, min(height - 1, int(boundary.bottom * height)))
        fired = self.left_punch or self.right_punch or self.left_haymaker or self.right_haymaker
        color = (80, 240, 80) if fired else (0, 190, 255)
        cv2.line(out, (x, top), (x, bottom), color, 2)
        label = "LEFT!" if self.left_punch or self.left_haymaker else "RIGHT!" if fired else "PUNCH"
        cv2.putText(out, label, (max(0, min(width - 65, x - 25)), max(14, top - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        return out

def _distance2d(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

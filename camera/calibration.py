"""Camera calibration with an explicit state machine for validation.

The game must NOT proceed to the next calibration step until the requested pose 
has actually been detected and held successfully.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import List, Optional

import config
from camera.pose_tracker import (LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER, 
                                 LM_LEFT_HIP, LM_RIGHT_HIP, 
                                 LM_LEFT_WRIST, LM_RIGHT_WRIST, 
                                 LM_LEFT_ELBOW, LM_RIGHT_ELBOW, 
                                 LM_NOSE, PoseData)

log = logging.getLogger(__name__)

# Steps in calibration
PHASE_START = 0
PHASE_NEUTRAL = 1
PHASE_ARMS_UP = 2
PHASE_GUARD = 3
PHASE_SIDE = 4
PHASE_DONE = 5

HOLD_TIME_REQ = 1.0


@dataclass
class CalibrationData:
    shoulder_width: float = config.DISTANCE_REF_FALLBACK
    torso_height: float = config.DISTANCE_REF_TORSO_FALLBACK
    neutral_x: float = 0.5
    timestamp: str = ""
    lead_shoulder: str = "left"  # "left" or "right"
    arm_length: float = 0.5 # normalized
    punch_direction: float = 0.0  # image-left (-1) or image-right (+1); 0 = legacy

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "CalibrationData":
        if not data:
            return cls()
        return cls(
            shoulder_width=float(data.get("shoulder_width", config.DISTANCE_REF_FALLBACK)),
            torso_height=float(data.get("torso_height", config.DISTANCE_REF_TORSO_FALLBACK)),
            neutral_x=float(data.get("neutral_x", 0.5)),
            timestamp=str(data.get("timestamp", "")),
            lead_shoulder=str(data.get("lead_shoulder", "left")),
            arm_length=float(data.get("arm_length", 0.5)),
            punch_direction=float(data.get("punch_direction", 0.0)),
        )


class Calibrator:
    """Collects pose samples with a state machine to validate poses."""

    def __init__(self, existing: Optional[CalibrationData] = None) -> None:
        self.existing = existing
        self.started = False
        
        self.phase = PHASE_START
        self.hold_time = 0.0
        
        self.tracking_lost = False
        self.body_not_detected = False
        
        # Temp buffers for measurements
        self._shoulders: List[float] = []
        self._torsos: List[float] = []
        self._centers: List[float] = []
        self._arm_lengths: List[float] = []
        self._z_diffs: List[float] = []
        self._punch_directions: List[float] = []
        
    def start(self) -> None:
        self.phase = PHASE_NEUTRAL
        self.hold_time = 0.0
        self.tracking_lost = False
        self.body_not_detected = False
        self._shoulders = []
        self._torsos = []
        self._centers = []
        self._arm_lengths = []
        self._z_diffs = []
        self._punch_directions = []
        self.started = True

    def process(self, pose: PoseData, dt: float) -> bool:
        """Processes one frame. Returns True if calibration is complete."""
        if not self.started or self.phase == PHASE_DONE:
            return True
            
        if not pose or not pose.present:
            self.tracking_lost = True
            self.hold_time = max(0.0, self.hold_time - dt * 2.0)
            return False
            
        self.tracking_lost = False

        # We need all key upper body parts visible
        ls = pose.lm(LM_LEFT_SHOULDER)
        rs = pose.lm(LM_RIGHT_SHOULDER)
        lh = pose.lm(LM_LEFT_HIP)
        rh = pose.lm(LM_RIGHT_HIP)
        lw = pose.lm(LM_LEFT_WRIST)
        rw = pose.lm(LM_RIGHT_WRIST)
        le = pose.lm(LM_LEFT_ELBOW)
        re = pose.lm(LM_RIGHT_ELBOW)
        nose = pose.lm(LM_NOSE)
        
        req = [ls, rs, lh, rh, lw, rw, le, re, nose]
        if any(v is None or v[3] < config.POSE_MIN_LANDMARK_VIS for v in req):
            self.body_not_detected = True
            self.hold_time = max(0.0, self.hold_time - dt * 2.0)
            return False
            
        self.body_not_detected = False
        
        # Helpers
        sw = abs(ls[0] - rs[0]) + 0.001
        torso_h = abs(((ls[1] + rs[1]) / 2) - ((lh[1] + rh[1]) / 2))
        
        if self.phase == PHASE_NEUTRAL:
            if self._is_neutral(pose, lw, rw, ls, rs, lh, rh):
                self.hold_time += dt
                self._shoulders.append(sw)
                self._torsos.append(torso_h)
                self._centers.append(pose.body_center_x)
                
                left_arm = _dist(ls, le) + _dist(le, lw)
                right_arm = _dist(rs, re) + _dist(re, rw)
                self._arm_lengths.append(max(left_arm, right_arm))
            else:
                self.hold_time = max(0.0, self.hold_time - dt * 1.5)
                
            if self.hold_time >= HOLD_TIME_REQ:
                self.phase = PHASE_ARMS_UP
                self.hold_time = 0.0
                
        elif self.phase == PHASE_ARMS_UP:
            if self._is_arms_up(pose, lw, rw, ls, rs):
                self.hold_time += dt
            else:
                self.hold_time = max(0.0, self.hold_time - dt * 1.5)
                
            if self.hold_time >= HOLD_TIME_REQ:
                self.phase = PHASE_GUARD
                self.hold_time = 0.0

        elif self.phase == PHASE_GUARD:
            if self._is_guard(pose, lw, rw, nose, sw):
                self.hold_time += dt
            else:
                self.hold_time = max(0.0, self.hold_time - dt * 1.5)
                
            if self.hold_time >= HOLD_TIME_REQ:
                self.phase = PHASE_SIDE
                self.hold_time = 0.0

        elif self.phase == PHASE_SIDE:
            if self._is_side_stance(pose, ls, rs, lw, rw, sw):
                self.hold_time += dt
                self._punch_directions.append(
                    (lw[0] + rw[0] - ls[0] - rs[0]) / 2.0)
                if not pose.is_2d:
                    self._z_diffs.append(ls[2] - rs[2])
                else:
                    self._z_diffs.append(ls[0] - rs[0])
            else:
                self.hold_time = max(0.0, self.hold_time - dt * 1.5)
                
            if self.hold_time >= HOLD_TIME_REQ:
                self.phase = PHASE_DONE
                self.hold_time = 0.0
                return True
                
        return False

    def finish(self) -> CalibrationData:
        import statistics
        import time
        
        z_diff = statistics.median(self._z_diffs) if self._z_diffs else -0.1
        lead_shoulder = "left" if z_diff < 0 else "right"
        hand_offset = statistics.median(self._punch_directions) if self._punch_directions else 0.0
        punch_direction = (1.0 if hand_offset > 0 else -1.0) if abs(hand_offset) > 0.02 else 0.0
        
        data = CalibrationData(
            shoulder_width=statistics.median(self._shoulders) if self._shoulders else config.DISTANCE_REF_FALLBACK,
            torso_height=statistics.median(self._torsos) if self._torsos else config.DISTANCE_REF_TORSO_FALLBACK,
            neutral_x=statistics.median(self._centers) if self._centers else 0.5,
            arm_length=statistics.median(self._arm_lengths) if self._arm_lengths else 0.5,
            timestamp=time.strftime("%Y-%m-%d %H:%M"),
            lead_shoulder=lead_shoulder,
            punch_direction=punch_direction,
        )
        log.info(f"Calibration complete: shoulder={data.shoulder_width:.3f} torso={data.torso_height:.3f} lead={data.lead_shoulder} arm={data.arm_length:.3f}")
        return data

    # ---- Validation Rules ----
    def _is_neutral(self, pose, lw, rw, ls, rs, lh, rh):
        # Hands below shoulders and near hips
        return lw[1] > ls[1] and rw[1] > rs[1] and abs(lw[0] - lh[0]) < 0.2 and abs(rw[0] - rh[0]) < 0.2

    def _is_arms_up(self, pose, lw, rw, ls, rs):
        # Wrists above shoulders
        return lw[1] < ls[1] - 0.05 and rw[1] < rs[1] - 0.05

    def _is_guard(self, pose, lw, rw, nose, sw):
        # Wrists near nose
        dl = _dist(lw, nose) / sw
        dr = _dist(rw, nose) / sw
        return dl < 1.5 and dr < 1.5

    def _is_side_stance(self, pose, ls, rs, lw, rw, sw):
        # Hands up (not neutral) and one shoulder closer / turned
        if lw[1] > ls[1] + 0.1 and rw[1] > rs[1] + 0.1:
            return False # hands too low
        # Shoulders are close together horizontally (side profile)
        return sw < 0.25  # In a strict side stance, shoulder width in 2D is very small


def _dist(a, b) -> float:
    return ((a[0] - b[0])**2 + (a[1] - b[1])**2)**0.5

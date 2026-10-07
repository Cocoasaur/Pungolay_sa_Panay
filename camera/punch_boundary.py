"""A punch line anchored to the current torso in camera coordinates."""

from dataclasses import dataclass
from typing import Optional

import config
from camera.pose_tracker import LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER


@dataclass(frozen=True)
class PunchBoundary:
    x: float
    top: float
    bottom: float
    direction: float
    arm_length: float

    def reach(self, wrist) -> float:
        """Signed hand distance beyond the line, measured in arm lengths."""
        return (wrist[0] - self.x) * self.direction / self.arm_length


def punch_boundary(pose, calibration, sensitivity: float = 1.0,
                   torso_height: Optional[float] = None) -> Optional[PunchBoundary]:
    if not pose.present:
        return None
    left = pose.lm(LM_LEFT_SHOULDER)
    right = pose.lm(LM_RIGHT_SHOULDER)
    if (left is None or right is None or
            min(left[3], right[3]) < config.POSE_MIN_LANDMARK_VIS):
        return None
    torso = pose.torso_height if torso_height is None else torso_height
    reference_torso = max(0.05, getattr(calibration, "torso_height", 0.36))
    if torso <= 0.05:
        torso = reference_torso
    # Use torso scale: shoulder width collapses in a side-on punching stance.
    scale = max(0.5, min(2.0, torso / reference_torso))
    arm = max(0.05, getattr(calibration, "arm_length", torso) * scale)
    direction = getattr(calibration, "punch_direction", 0.0)
    if direction not in (-1.0, 1.0):
        direction = -1.0 if getattr(calibration, "lead_shoulder", "left") == "right" else 1.0
    center_x = (left[0] + right[0]) / 2.0
    shoulder_y = (left[1] + right[1]) / 2.0
    reach = config.PUNCH_LINE_REACH / max(0.5, min(3.0, sensitivity))
    return PunchBoundary(center_x + direction * arm * reach,
                         shoulder_y - torso * 0.25,
                         shoulder_y + torso * 0.65, direction, arm)

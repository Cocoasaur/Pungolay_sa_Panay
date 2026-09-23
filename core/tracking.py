"""Logical input abstraction between the computer-vision pipeline / keyboard
and the gameplay code.

Gameplay never touches raw OpenCV or MediaPipe coordinates. Everything the
player needs arrives packed in a TrackingData instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrackingData:
    """The single interface gameplay consumes as "player input".

    `present` is False whenever the camera is off, the pose is lost or the
    keyboard mode was disabled -- gameplay must then freeze movement instead
    of teleporting the fighter.
    """

    present: bool = False
    horizontal_position: float = 0.5   # 0.0 (left) .. 1.0 (right)
    distance_ratio: float = 1.0        # relative scale vs calibration reference
    distance_level: str = "MEDIUM"     # "CLOSE" | "MEDIUM" | "FAR"
    left_punch: bool = False           # edge-triggered
    right_punch: bool = False          # edge-triggered
    left_haymaker: bool = False
    right_haymaker: bool = False
    is_charging: bool = False
    is_charged: bool = False
    charge_progress: float = 0.0
    guard: bool = False
    hands_up: bool = False             # both hands raised (knockdown get-up)
    player_scale: float = 1.0          # fighter sprite scale from distance

    # Debug / HUD information (never used by gameplay logic)
    body_confidence: float = 0.0
    pose_present: bool = False
    frame_w: int = 0
    frame_h: int = 0
    debug: dict = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "TrackingData":
        return cls()
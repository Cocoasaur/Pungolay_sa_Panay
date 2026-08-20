"""Camera calibration.

Collects reference body measurements while the player stands still in front
of the camera: normalized shoulder width, torso height and neutral horizontal
position. The median of a short sample window is stored so single bad frames
cannot poison the reference values.

Calibration is a *relative* reference used by the distance estimator -- it
never claims to know real centimeters (see spec section 50).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import config

log = logging.getLogger(__name__)

CALIBRATION_SAMPLES = 24          # frames to collect before finishing
CALIBRATION_MAX_SAMPLES = 120     # hard cap so calibration always ends


@dataclass
class CalibrationData:
    shoulder_width: float = config.DISTANCE_REF_FALLBACK
    torso_height: float = config.DISTANCE_REF_TORSO_FALLBACK
    neutral_x: float = 0.5
    samples: int = 0
    timestamp: str = ""

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
            samples=int(data.get("samples", 0)),
            timestamp=str(data.get("timestamp", "")),
        )


class Calibrator:
    """Collects pose samples and produces a CalibrationData when done."""

    def __init__(self, existing: Optional[CalibrationData] = None) -> None:
        self.existing = existing
        self._shoulders: List[float] = []
        self._torsos: List[float] = []
        self._centers: List[float] = []
        self.started = False

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._shoulders = []
        self._torsos = []
        self._centers = []
        self.started = True

    @property
    def progress(self) -> float:
        """0..1 progress towards a full sample set."""
        return min(1.0, len(self._shoulders) / CALIBRATION_SAMPLES)

    def add_sample(self, pose) -> bool:
        """Feed one pose frame. Returns True when calibration is complete."""
        if not pose.present:
            return False
        if pose.shoulder_width > 0.03 and pose.torso_height > 0.05:
            self._shoulders.append(pose.shoulder_width)
            self._torsos.append(pose.torso_height)
            self._centers.append(pose.body_center_x)
        return len(self._shoulders) >= CALIBRATION_SAMPLES

    def finish(self) -> CalibrationData:
        """Median of the collected samples -> stable reference values."""
        import statistics
        import time
        data = CalibrationData(
            shoulder_width=statistics.median(self._shoulders)
            if self._shoulders else config.DISTANCE_REF_FALLBACK,
            torso_height=statistics.median(self._torsos)
            if self._torsos else config.DISTANCE_REF_TORSO_FALLBACK,
            neutral_x=statistics.median(self._centers)
            if self._centers else 0.5,
            samples=len(self._shoulders),
            timestamp=time.strftime("%Y-%m-%d %H:%M"),
        )
        log.info("Calibration complete: shoulder=%.3f torso=%.3f",
                 data.shoulder_width, data.torso_height)
        return data
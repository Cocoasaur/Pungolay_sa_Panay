"""Fresh-sample lateral intent: noise holds position, reacquisition rebases it."""

from collections import deque
from statistics import median
import config
from camera.pose_tracker import LM_LEFT_HIP, LM_RIGHT_HIP


class MovementController:
    def __init__(self, position=config.DEPTH_NEUTRAL_HP):
        self.position = position
        self.state = "REACQUIRING"
        self._window = deque(maxlen=3)
        self._anchor = None
        self._held_position = position
        self._last = None
        self._candidate = 0.0
        self._still = 0.0
        self._stable = 0.0
        self._outlier = None

    @property
    def valid(self):
        return self.state in ("HOLDING", "MOVING")

    def recenter(self, position=None):
        self.__init__(self.position if position is None else position)

    def lose(self):
        self.state = "TRACKING LOST"
        self._window.clear()
        self._stable = 0.0
        self._last = None
        self._candidate = self._still = 0.0
        return self.position

    def update(self, pose, dt, mirror=True, sensitivity=1.0):
        points = [pose.lm(i) for i in (LM_LEFT_HIP, LM_RIGHT_HIP)] if pose and pose.present else []
        if len(points) != 2 or any(
            p is None or p[3] < config.MOVEMENT_MIN_CONFIDENCE for p in points
        ):
            return self.lose()
        x = sum(p[0] for p in points) / 2
        if mirror:
            x = 1 - x
        dt = max(0.001, min(0.25, dt))
        if self._last is not None and abs(x - self._last) > config.MOVEMENT_MAX_SAMPLE_JUMP:
            if self._outlier is None or abs(x - self._outlier) > 0.025:
                self._outlier = x
                self.state = "REACQUIRING"
                self._stable = 0
                self._window.clear()
                return self.position
            self._outlier = None
        else:
            self._outlier = None
        self._window.append(x)
        center = median(self._window)
        if not self.valid:
            if self._last is None or abs(center - self._last) < 0.015:
                self._stable += dt
            else:
                self._stable = 0
            self._last = center
            self.state = "REACQUIRING"
            if self._stable >= config.MOVEMENT_REACQUIRE_TIME:
                self._anchor = center
                self._held_position = self.position
                self.state = "HOLDING"
                self._candidate = self._still = 0.0
            return self.position
        velocity = abs(center - self._last) / dt if self._last is not None else 0
        self._last = center
        displacement = center - self._anchor
        if self.state == "HOLDING":
            self._candidate = (
                self._candidate + dt if abs(displacement) >= config.MOVEMENT_ENTER_DISTANCE else 0
            )
            if self._candidate < config.MOVEMENT_ENTER_TIME:
                return self.position
            self.state = "MOVING"
            self._still = 0
        self.position = max(
            config.DEPTH_HP_MIN,
            min(config.DEPTH_HP_MAX, self._held_position + displacement * sensitivity),
        )
        self._still = self._still + dt if velocity < config.MOVEMENT_STOP_VELOCITY else 0
        if self._still >= config.MOVEMENT_STOP_TIME:
            self.state = "HOLDING"
            self._anchor = center
            self._held_position = self.position
            self._candidate = 0
        return self.position

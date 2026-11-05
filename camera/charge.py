"""Torso-relative charge recognition with explicit observed-time accounting."""

import math
import config
from camera.pose_tracker import (
    LM_LEFT_SHOULDER,
    LM_RIGHT_SHOULDER,
    LM_LEFT_ELBOW,
    LM_RIGHT_ELBOW,
    LM_LEFT_WRIST,
    LM_RIGHT_WRIST,
)


class ChargeController:
    def __init__(self):
        self.hands = {
            side: dict(
                entry=0.0, elapsed=0.0, released=0.0, last_seen=None, completed=False, paused=False
            )
            for side in ("left", "right")
        }
        self.completed = False
        self.side = ""
        self.progress = 0.0
        self.active = False
        self.ready = False
        self.hint = "Pull one glove back beside your chest"

    @staticmethod
    def candidate(pose, side, calibration):
        indices = (
            (LM_LEFT_SHOULDER, LM_LEFT_ELBOW, LM_LEFT_WRIST)
            if side == "left"
            else (LM_RIGHT_SHOULDER, LM_RIGHT_ELBOW, LM_RIGHT_WRIST)
        )
        points = [pose.lm(i) for i in indices] if pose and pose.present else []
        if len(points) != 3 or any(p is None or p[3] < 0.55 for p in points):
            return None
        shoulder, elbow, wrist = points
        torso = max(0.1, pose.torso_height or getattr(calibration, "torso_height", 0.36))
        arm = max(0.15, getattr(calibration, "arm_length", torso))
        direction = getattr(calibration, "punch_direction", 1.0)
        if direction not in (-1.0, 1.0):
            direction = -1.0 if getattr(calibration, "lead_shoulder", "left") == "right" else 1.0
        aspect = (pose.frame_w or 640) / (pose.frame_h or 360)
        a = (
            (shoulder[0] - elbow[0]) * aspect,
            shoulder[1] - elbow[1],
            0 if pose.is_2d else (shoulder[2] - elbow[2]) * aspect,
        )
        b = (
            (wrist[0] - elbow[0]) * aspect,
            wrist[1] - elbow[1],
            0 if pose.is_2d else (wrist[2] - elbow[2]) * aspect,
        )
        length = math.sqrt(sum(v * v for v in a) * sum(v * v for v in b))
        if length < 1e-5:
            return False
        angle = math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(a, b)) / length))))
        pulled = (wrist[0] - shoulder[0]) * direction < -0.04 * arm
        if not pose.is_2d:
            pulled = pulled or wrist[2] - shoulder[2] > 0.06 * arm
        chest = shoulder[1] - 0.04 * torso <= wrist[1] <= shoulder[1] + 0.70 * torso
        close = math.hypot(wrist[0] - shoulder[0], wrist[1] - shoulder[1]) < 0.85 * arm
        return pulled and chest and close and angle < 115

    def update(self, pose, dt, calibration, now):
        self.completed = False
        for side, hand in self.hands.items():
            candidate = self.candidate(pose, side, calibration)
            if candidate is None:
                hand["paused"] = hand["elapsed"] > 0
                if (
                    hand["last_seen"] is not None
                    and now - hand["last_seen"] >= config.CHARGE_LOST_GRACE
                ):
                    hand.update(entry=0.0, elapsed=0.0, released=0.0, completed=False, paused=False)
                continue
            previous = hand["last_seen"]
            hand["last_seen"] = now
            observed_dt = (
                min(dt, max(0, now - previous)) if previous is not None else min(dt, 1 / 30)
            )
            if hand["paused"]:
                observed_dt = 0
            hand["paused"] = False
            if candidate:
                hand["released"] = 0
                hand["entry"] += observed_dt
                if hand["entry"] >= config.CHARGE_ENTRY_TIME:
                    hand["elapsed"] += observed_dt
                    if (
                        hand["elapsed"] + 1e-8 >= config.HAYMAKER_CHARGE_TIME
                        and not hand["completed"]
                    ):
                        hand["elapsed"] = config.HAYMAKER_CHARGE_TIME
                        hand["completed"] = True
                        self.completed = True
            else:
                hand["released"] += observed_dt
                if hand["released"] + 1e-8 >= config.CHARGE_RELEASE_GRACE:
                    hand.update(entry=0.0, elapsed=0.0, completed=False, paused=False)
        side, hand = max(self.hands.items(), key=lambda p: p[1]["elapsed"])
        self.active = hand["elapsed"] > 0
        self.side = side if self.active else ""
        self.progress = min(1, hand["elapsed"] / config.HAYMAKER_CHARGE_TIME)
        self.ready = hand["completed"]
        self.hint = (
            "Tracking interrupted — hold your pose"
            if hand["paused"]
            else (
                "Hold your glove beside your chest"
                if self.active
                else "Pull one glove back beside your chest"
            )
        )
        if hand["released"] > 0 and self.active and not hand["completed"]:
            self.hint = "Bring your glove back beside your chest"
        return self.completed

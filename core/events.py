"""Tiny publish/subscribe bus used to decouple gameplay from audio/UI hooks.

The combat system emits events (PUNCH, HIT, BLOCK, KNOCKDOWN, VICTORY,
DEFEAT); the audio manager subscribes to them. Nothing crashes if nobody
listens.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event: str, callback: Callable) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    def emit(self, event: str, **payload: Any) -> None:
        for cb in self._subscribers.get(event, []):
            try:
                cb(**payload)
            except Exception:
                log.exception("Event handler for %r failed", event)
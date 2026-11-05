"""Background atlas decoding; only small surface uploads occur on the UI thread."""

from collections import OrderedDict
import queue
import threading
import time
import cv2
import pygame
import config


class AnimationCache:
    def __init__(self):
        self.frames = OrderedDict()
        self.bytes = 0
        self.queued_bytes = 0
        self.failed = set()
        self.pending = set()
        self._lock = threading.Lock()
        self._jobs = queue.Queue()
        self._done = queue.Queue()
        self._thread = None
        self._generation = 0
        self._source_bytes = 0

    @property
    def memory_bytes(self):
        return self.bytes + self.queued_bytes + self._source_bytes

    def request(self, key):
        if key in self.frames:
            self.frames.move_to_end(key)
            return self.frames[key]
        if key in self.failed:
            return None
        with self._lock:
            if (self._generation, key) not in self.pending:
                self.pending.add((self._generation, key))
                self._jobs.put((self._generation, key))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._decode, daemon=True)
                self._thread.start()
        return None

    def _decode(self):
        source_path = None
        source = None
        while True:
            try:
                generation, key = self._jobs.get(timeout=0.5)
            except queue.Empty:
                with self._lock:
                    if self._jobs.empty():
                        self._thread = None
                        self._source_bytes = 0
                        return
                continue
            if generation != self._generation:
                with self._lock:
                    self.pending.discard((generation, key))
                continue
            path, rect, width, height, facing = key
            try:
                if source_path != path:
                    source = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                    source_path = path
                    self._source_bytes = source.nbytes if source is not None else 0
                if source is None:
                    raise ValueError("Unavailable atlas")
                x, y, w, h = rect
                frame = source[y : y + h, x : x + w]
                if frame.shape[:2] != (h, w):
                    raise ValueError("Invalid atlas rectangle")
                frame = cv2.cvtColor(
                    frame, cv2.COLOR_BGRA2RGBA if frame.shape[2] == 4 else cv2.COLOR_BGR2RGBA
                )
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                if facing < 0:
                    frame = cv2.flip(frame, 1)
                pixels = frame.tobytes()
                while (
                    self.queued_bytes + len(pixels) > 16 * 1024 * 1024
                    and generation == self._generation
                ):
                    time.sleep(0.005)
                if generation != self._generation:
                    with self._lock:
                        self.pending.discard((generation, key))
                    continue
                with self._lock:
                    self.queued_bytes += len(pixels)
                self._done.put((generation, key, pixels))
            except (ValueError, cv2.error, OSError):
                with self._lock:
                    self.failed.add(key)
                    self.pending.discard((generation, key))

    def pump(self, budget_ms=2):
        start = time.perf_counter()
        while (time.perf_counter() - start) * 1000 < budget_ms:
            try:
                generation, key, pixels = self._done.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                self.queued_bytes -= len(pixels)
                self.pending.discard((generation, key))
            if generation != self._generation:
                continue
            _, _, width, height, _ = key
            surface = pygame.image.frombuffer(pixels, (width, height), "RGBA").convert_alpha()
            size = surface.get_bytesize() * width * height
            limit = config.ANIMATION_CACHE_BYTES - 32 * 1024 * 1024
            while self.frames and self.bytes + size > limit:
                _, old = self.frames.popitem(last=False)
                self.bytes -= old.get_bytesize() * old.get_width() * old.get_height()
            old = self.frames.pop(key, None)
            if old is not None:
                self.bytes -= old.get_bytesize() * old.get_width() * old.get_height()
            self.frames[key] = surface
            self.bytes += size

    def cancel(self):
        self._generation += 1
        with self._lock:
            self.pending.clear()
        self.frames.clear()
        self.bytes = 0

    def wait_ready(self, timeout=15):
        """Offline validation helper; gameplay never waits on asset decoding."""
        deadline = time.monotonic() + timeout
        while self.pending and time.monotonic() < deadline:
            self.pump(5)
            time.sleep(0.002)
        self.pump(5)
        return not self.pending


cache = AnimationCache()

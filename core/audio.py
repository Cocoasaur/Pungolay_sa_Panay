"""Audio manager with procedurally generated placeholder sounds.

Sound files are synthesized with numpy on first run (no external downloads,
no licensing issues). If pygame.mixer cannot initialize or a file is missing
the game keeps running silently -- audio is a hook, never a requirement.
"""

from __future__ import annotations

import logging
import os
import struct
import wave

import numpy as np

import config

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050

# name -> (duration, synthesizer function)
def _menu_move() -> np.ndarray:
    return _blip(0.06, 720, 520)

def _menu_select() -> np.ndarray:
    return np.concatenate([_blip(0.07, 560, 560), _blip(0.09, 880, 880)])

def _punch_swing() -> np.ndarray:
    return _noise(0.14, 0.35)  # soft whoosh

def _hit() -> np.ndarray:
    return _noise(0.12, 1.0) + 0.9 * _sine(0.12, 120, decay=9)

def _block() -> np.ndarray:
    return _mix(0.6 * _sine(0.07, 480, decay=18), 0.4 * _noise(0.05, 0.5))

def _knockdown() -> np.ndarray:
    return _mix(_sine(0.5, 70, decay=3.2), 0.3 * _noise(0.35, 0.4))

def _victory() -> np.ndarray:
    out = []
    for f in (523, 659, 784, 1047):
        out.append(_sine(0.18, f, decay=6))
        out.append(np.zeros(int(0.02 * SAMPLE_RATE)))
    return np.concatenate(out)

def _defeat() -> np.ndarray:
    out = []
    for f in (392, 311, 262, 196):
        out.append(_sine(0.22, f, decay=5))
        out.append(np.zeros(int(0.02 * SAMPLE_RATE)))
    return np.concatenate(out)

def _sine(dur: float, freq: float, decay: float = 8.0) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n, endpoint=False)
    wave_ = np.sin(2 * np.pi * freq * t) * np.exp(-decay * t)
    return wave_ * 0.55

def _blip(dur: float, f_start: float, f_end: float) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = np.linspace(f_start, f_end, n)
    wave_ = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)
    env = np.minimum(1.0, t / 0.01) * np.exp(-8 * t)
    return wave_ * env * 0.6

def _noise(dur: float, gain: float) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    wave_ = np.random.uniform(-1, 1, n) * np.exp(-10 * np.linspace(0, dur, n))
    return wave_ * gain

def _mix(*waves: np.ndarray) -> np.ndarray:
    """Sum several waveforms, padding shorter ones with silence."""
    length = max(w.size for w in waves)
    out = np.zeros(length)
    for wave_ in waves:
        out[:wave_.size] += wave_
    return out

SOUNDS = {
    "menu_move": _menu_move,
    "menu_select": _menu_select,
    "punch": _punch_swing,
    "hit": _hit,
    "block": _block,
    "knockdown": _knockdown,
    "victory": _victory,
    "defeat": _defeat,
}


def generate_sound_files(sounds_dir: str = config.SOUNDS_DIR) -> None:
    """Synthesize every placeholder wav (idempotent, only fills gaps)."""
    os.makedirs(sounds_dir, exist_ok=True)
    for name, synth in SOUNDS.items():
        path = os.path.join(sounds_dir, f"{name}.wav")
        if os.path.exists(path):
            continue
        data = synth()
        data = np.clip(data, -1.0, 1.0)
        pcm = (data * 32767).astype(np.int16)
        try:
            with wave.open(path, "wb") as fh:
                fh.setnchannels(1)
                fh.setsampwidth(2)
                fh.setframerate(SAMPLE_RATE)
                fh.writeframes(pcm.tobytes())
        except OSError:
            log.exception("Could not write sound %s", path)


class AudioManager:
    def __init__(self) -> None:
        self._enabled = False
        self._sounds = {}
        self._music_volume = float(config.DEFAULT_SETTINGS["music_volume"])
        self._sfx_volume = float(config.DEFAULT_SETTINGS["sfx_volume"])
        try:
            import pygame
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
            self._enabled = True
        except Exception:
            log.warning("Audio unavailable; game will run silent.")
            return
        generate_sound_files()
        for name in SOUNDS:
            path = os.path.join(config.SOUNDS_DIR, f"{name}.wav")
            if os.path.exists(path):
                try:
                    self._sounds[name] = pygame.mixer.Sound(path)
                except Exception:
                    log.warning("Could not load sound %s", name)

    # -- volume hooks (called by the settings screen) --------------------
    def set_volumes(self, music: float, sfx: float) -> None:
        self._music_volume = music
        self._sfx_volume = sfx

    def play(self, name: str, volume: float = 1.0) -> None:
        """Play a one-shot sound effect; no-ops when audio is unavailable."""
        if not self._enabled:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        try:
            sound.set_volume(min(1.0, self._sfx_volume * volume))
            sound.play()
        except Exception:
            pass

    def stop_all(self) -> None:
        if self._enabled:
            try:
                import pygame
                pygame.mixer.stop()
            except Exception:
                pass
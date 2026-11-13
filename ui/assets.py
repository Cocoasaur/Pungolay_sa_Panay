"""Shared decoded image cache, keyed by real path and output size."""

from functools import lru_cache
from pathlib import Path
import pygame


def load_image(path, size=None, alpha=True):
    if not Path(path).is_file():
        return None
    return _decode(path, size, alpha)


@lru_cache(maxsize=12)
def _decode(path, size, alpha):
    try:
        image = pygame.image.load(path)
        image = image.convert_alpha() if alpha else image.convert()
        if size and image.get_size() != size:
            image = pygame.transform.smoothscale(image, size)
        return image
    except (pygame.error, OSError):
        return None

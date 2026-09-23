"""PUNGOLAY SA PANAY - entry point.

Runs the game; any uncaught error is printed with a friendly note instead of
a bare traceback-less exit.
"""

from __future__ import annotations

import logging
import sys
import traceback


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(name)s: %(message)s")
    try:
        from core.game import Game
        Game().run()
    except Exception:
        print("=" * 60)
        print("PUNGOLAY SA PANAY hit an unexpected error:")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        print("Tip: check that your webcam is connected. The game also runs")
        print("in KEYBOARD MODE via SETTINGS -> INPUT MODE.")
        sys.exit(1)


if __name__ == "__main__":
    main()
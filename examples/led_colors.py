#!/usr/bin/env python3
"""
led_colors.py — Cycle the DualSense light bar through a rainbow and named colours.
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.utils.color import rgb_from_hsv, named_color, COLORS


def main():
    with DualSense() as ds:
        # 1. Rainbow sweep (HSV hue 0→1)
        print("Rainbow sweep …")
        steps = 60
        for i in range(steps + 1):
            h = i / steps
            r, g, b = rgb_from_hsv(h, 1.0, 1.0)
            ds.set_led(r, g, b)
            time.sleep(0.05)

        # 2. Named colour presets
        print("Named colour presets …")
        for name in ("red", "green", "blue", "yellow", "cyan", "magenta",
                     "orange", "purple", "white", "off"):
            r, g, b = named_color(name)
            print(f"  {name}: ({r},{g},{b})")
            ds.set_led(r, g, b)
            time.sleep(0.6)

        # 3. Player-colour defaults
        print("Player indicator colours …")
        for p in range(1, 5):
            r, g, b = named_color(f"player{p}")
            ds.set_led(r, g, b)
            time.sleep(0.5)

        ds.set_led(0, 0, 64)
        print("Done.")


if __name__ == "__main__":
    main()

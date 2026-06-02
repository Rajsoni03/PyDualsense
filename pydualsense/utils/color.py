"""
Colour helpers for the DualSense light bar.
"""

import colorsys
from typing import Tuple

Color = Tuple[int, int, int]   # (R, G, B) each 0–255

# Named presets
COLORS = {
    "red":     (255,   0,   0),
    "green":   (  0, 255,   0),
    "blue":    (  0,   0, 255),
    "white":   (255, 255, 255),
    "off":     (  0,   0,   0),
    "yellow":  (255, 255,   0),
    "cyan":    (  0, 255, 255),
    "magenta": (255,   0, 255),
    "orange":  (255, 128,   0),
    "purple":  (128,   0, 255),
    "pink":    (255,  20, 147),
    # Player defaults
    "player1": (  0,   0, 255),   # Blue
    "player2": (255,   0,   0),   # Red
    "player3": (  0, 255,   0),   # Green
    "player4": (255,   0, 255),   # Magenta
}


def named_color(name: str) -> Color:
    """Return (R, G, B) for a colour name, or raise KeyError."""
    return COLORS[name.lower()]


def rgb_from_hsv(h: float, s: float, v: float) -> Color:
    """Convert HSV (each 0.0–1.0) to (R, G, B) each 0–255."""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

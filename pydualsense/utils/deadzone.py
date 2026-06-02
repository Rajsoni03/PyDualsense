"""
Deadzone processing for analog sticks.

All functions work on normalised values in the range −1.0 to +1.0.
"""

import math


def apply_deadzone(value: float, threshold: float) -> float:
    """Apply a symmetric deadzone to a single axis.

    Values within ±threshold are snapped to 0; the remainder is rescaled
    so the output spans the full −1 … +1 range.
    """
    if abs(value) < threshold:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - threshold) / (1.0 - threshold)


def apply_deadzone_circular(x: float, y: float, threshold: float) -> tuple:
    """Apply a circular (radial) deadzone to a 2-D stick.

    Points inside the circle of radius *threshold* snap to (0, 0).
    The remainder is rescaled to preserve the full range.

    Returns:
        (x, y) after deadzone application.
    """
    magnitude = math.sqrt(x * x + y * y)
    if magnitude < threshold:
        return 0.0, 0.0
    scale = (magnitude - threshold) / (1.0 - threshold) / magnitude
    return x * scale, y * scale


def apply_deadzone_square(x: float, y: float, threshold: float) -> tuple:
    """Apply independent per-axis deadzones (square shape)."""
    return apply_deadzone(x, threshold), apply_deadzone(y, threshold)

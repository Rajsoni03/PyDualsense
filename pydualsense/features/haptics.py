"""
Rumble / haptic motor helpers.

right_motor = small, high-frequency (right grip)
left_motor  = large, low-frequency  (left grip)
Both are 0–255.
"""


def clamp(value: int) -> int:
    return max(0, min(255, int(value)))

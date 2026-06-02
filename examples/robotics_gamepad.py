#!/usr/bin/env python3
"""
robotics_gamepad.py — Gamepad-to-robot-command example.

Maps DualSense inputs to a simple differential-drive robot command interface.
Adapt the `drive()` function to your actual robot communication layer.

Controls:
    Left stick  Y → forward / backward speed
    Right stick X → turn rate (left / right)
    R2          → boost multiplier (hold for max speed)
    Circle      → emergency stop
    Triangle    → toggle LED indicator
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState
from pydualsense.utils.deadzone import apply_deadzone_circular

DEADZONE = 0.10
led_on = True


def drive(forward: float, turn: float):
    """Stub: replace with actual robot control (ROS, serial, etc.)."""
    left_wheel  = forward + turn
    right_wheel = forward - turn
    # print(f"  L={left_wheel:+.2f}  R={right_wheel:+.2f}")   # uncomment to debug


def on_state(state: InputState):
    global led_on

    # Sticks → (forward, turn) in −1 … +1
    nx, ny = state.left_stick.normalised()
    rx, ry = state.right_stick.normalised()
    nx, ny = apply_deadzone_circular(nx, ny, DEADZONE)
    rx, ry = apply_deadzone_circular(rx, ry, DEADZONE)

    forward = -ny               # Y-up = forward
    turn    = rx
    boost   = state.r2 / 255.0 # R2 analog as 0–1 boost

    speed = 0.5 + 0.5 * boost  # 50–100% speed range
    drive(forward * speed, turn * speed)

    # Emergency stop
    if state.buttons.circle:
        drive(0.0, 0.0)

    # LED toggle on triangle press
    if state.buttons.triangle:
        led_on = not led_on
        # (edge detection would be better here; this fires every frame)


def main():
    with DualSense() as ds:
        ds.set_led(0, 200, 0)   # green = ready
        print("Robotics gamepad — move left stick to drive, R2 to boost, ○ to stop.")
        ds.listen(on_state)


if __name__ == "__main__":
    main()

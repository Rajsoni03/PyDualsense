#!/usr/bin/env python3
"""
basic_input.py — Print all DualSense controller state to the terminal.

Run:
    python examples/basic_input.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState


def fmt_stick(stick):
    nx, ny = stick.normalised()
    return f"({nx:+.2f},{ny:+.2f})"


def fmt_dpad(d):
    return d.name


def fmt_touch(tp):
    fingers = []
    for f in (tp.finger0, tp.finger1):
        if f.active:
            fingers.append(f"[id={f.id} x={f.x} y={f.y}]")
    return " ".join(fingers) or "—"


def on_state(state: InputState):
    b = state.buttons
    pressed = [name for name in vars(b) if getattr(b, name)]

    line = (
        f"\r"
        f"L:{fmt_stick(state.left_stick)}  R:{fmt_stick(state.right_stick)}  "
        f"L2:{state.l2:3d}  R2:{state.r2:3d}  "
        f"D:{fmt_dpad(state.dpad)}  "
        f"Btns:[{','.join(pressed) or '—':30s}]  "
        f"Touch:{fmt_touch(state.touchpad)}  "
        f"Gyro:({state.gyro.x:+6d},{state.gyro.y:+6d},{state.gyro.z:+6d})  "
        f"Bat:{state.battery.level}%{'C' if state.battery.charging else ' '}"
    )
    print(line, end="", flush=True)


def main():
    ds = DualSense()
    print("Connecting to DualSense controller…")
    ds.connect()
    print("Connected!  Press Ctrl-C to quit.\n")
    try:
        ds.listen(on_state)
    finally:
        ds.disconnect()
        print()


if __name__ == "__main__":
    main()

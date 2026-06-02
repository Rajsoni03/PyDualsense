#!/usr/bin/env python3
"""
touchpad_viz.py — Live ASCII visualisation of touchpad finger positions.

Touchpad resolution: 1920 × 1080.  Scaled to terminal width × 20 rows.
"""

import sys, os, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState

COLS, _ = shutil.get_terminal_size()
COLS = min(COLS - 2, 80)
ROWS = 20
TP_W, TP_H = 1920, 1080


def render(state: InputState):
    grid = [[" "] * COLS for _ in range(ROWS)]

    for finger in (state.touchpad.finger0, state.touchpad.finger1):
        if finger.active:
            col = int(finger.x / TP_W * (COLS - 1))
            row = int(finger.y / TP_H * (ROWS - 1))
            label = str(finger.id % 10)
            grid[row][col] = label

    top    = "┌" + "─" * COLS + "┐"
    bottom = "└" + "─" * COLS + "┘"

    lines = [top]
    for row in grid:
        lines.append("│" + "".join(row) + "│")
    lines.append(bottom)
    lines.append(f"  Touch: {'YES' if state.touchpad.touching else 'no ':3s}  "
                 f"Click: {'YES' if state.buttons.touchpad_click else 'no '}")

    # Overwrite from top of block
    move_up = f"\033[{len(lines)}A"
    print(move_up + "\n".join(lines), flush=True)


def main():
    ds = DualSense()
    ds.connect()
    print("Touchpad visualiser — slide fingers across the pad.  Ctrl-C to quit.")
    # Print blank lines to reserve space
    blank = ("│" + " " * COLS + "│\n") * ROWS
    print("┌" + "─" * COLS + "┐\n" + blank + "└" + "─" * COLS + "┘")
    try:
        ds.listen(render)
    finally:
        ds.disconnect()
        print()


if __name__ == "__main__":
    main()

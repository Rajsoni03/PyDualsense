#!/usr/bin/env python3
"""
rumble_demo.py — Demonstrate rumble patterns.

Cycles through: left only → right only → both → off.
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense


def main():
    with DualSense() as ds:
        print("Rumble demo — hold the controller!")

        patterns = [
            ("Left motor (large/LF) only",  0,   200),
            ("Right motor (small/HF) only", 200,   0),
            ("Both motors full",             255, 255),
            ("Both motors low",               64,  64),
            ("Off",                            0,   0),
        ]

        for label, right, left in patterns:
            print(f"  {label}")
            ds.set_rumble(right=right, left=left)
            time.sleep(1.0)

        print("Done.")


if __name__ == "__main__":
    main()

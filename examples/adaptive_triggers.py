#!/usr/bin/env python3
"""
adaptive_triggers.py — Cycle through all adaptive trigger modes.

Each mode is applied to both triggers for 2 seconds so you can
feel the effect.  Press Ctrl-C to skip to the next mode.
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.features.triggers import TriggerEffect


DEMOS = [
    ("Off",                   TriggerEffect.off()),
    ("Feedback (mid)",        TriggerEffect.feedback(start=60, force=160)),
    ("Weapon (pistol)",       TriggerEffect.weapon(start=40, end=100, force=220)),
    ("Vibration (engine)",    TriggerEffect.vibration(position=0, amplitude=200, frequency=30)),
    ("Slope (bow tension)",   TriggerEffect.slope(start=0, end=255, start_force=0, end_force=255)),
    ("Rigid (lock)",          TriggerEffect.rigid()),
    ("Multi-pos (3 clicks)",  TriggerEffect.multi_pos([50, 120, 200], [180, 180, 180])),
]


def wait(seconds, label):
    print(f"  [{label}] — hold for {seconds}s …", end="", flush=True)
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        pass
    print()


def main():
    with DualSense() as ds:
        print("Adaptive trigger demo — grip both triggers!\n")
        for name, effect in DEMOS:
            ds.set_trigger_effect("right", effect)
            ds.set_trigger_effect("left",  effect)
            wait(5.0, name)

        ds.set_trigger_off()
        print("\nAll done.")


if __name__ == "__main__":
    main()

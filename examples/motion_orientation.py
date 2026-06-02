#!/usr/bin/env python3
"""
motion_orientation.py — Live display of gyroscope and accelerometer values.

Shows raw counts and converted physical units (°/s and g).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState
from pydualsense.features.motion import MotionState, GYRO_SCALE, ACCEL_SCALE


def on_state(state: InputState):
    ms = MotionState(gyro=state.gyro, accel=state.accel)
    gx, gy, gz = ms.gyro_dps()
    ax, ay, az = ms.accel_g()
    print(
        f"\r"
        f"Gyro(°/s): X={gx:+7.1f}  Y={gy:+7.1f}  Z={gz:+7.1f}    "
        f"Accel(g):  X={ax:+5.3f}  Y={ay:+5.3f}  Z={az:+5.3f}",
        end="", flush=True,
    )


def main():
    ds = DualSense()
    ds.connect()
    print("Motion sensor readout — rotate the controller.  Ctrl-C to quit.\n")
    try:
        ds.listen(on_state)
    finally:
        ds.disconnect()
        print()


if __name__ == "__main__":
    main()

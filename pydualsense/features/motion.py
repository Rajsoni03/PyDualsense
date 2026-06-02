"""
IMU motion sensor helpers.

Raw gyroscope values are in units of ~16.4 LSB/°/s (ICM-42688-P at ±2000 °/s).
Raw accelerometer values are in units of ~8192 LSB/g (at ±4 g range).
"""

from dataclasses import dataclass
from ..protocol.input_report import Vec3

GYRO_SCALE = 1.0 / 16.4    # LSB → °/s
ACCEL_SCALE = 1.0 / 8192.0  # LSB → g


@dataclass
class MotionState:
    gyro: Vec3
    accel: Vec3

    def gyro_dps(self) -> tuple:
        """Return (gx, gy, gz) in degrees per second."""
        return (
            self.gyro.x * GYRO_SCALE,
            self.gyro.y * GYRO_SCALE,
            self.gyro.z * GYRO_SCALE,
        )

    def accel_g(self) -> tuple:
        """Return (ax, ay, az) in g (Earth gravities)."""
        return (
            self.accel.x * ACCEL_SCALE,
            self.accel.y * ACCEL_SCALE,
            self.accel.z * ACCEL_SCALE,
        )

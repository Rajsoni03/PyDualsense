"""
Simple signal filters for IMU data.
"""


class LowPassFilter:
    """Exponential moving-average low-pass filter for a scalar signal.

    alpha=1.0 means no filtering (pass-through); alpha→0 means heavy smoothing.
    """

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self._value: float = 0.0
        self._initialized = False

    def update(self, measurement: float) -> float:
        if not self._initialized:
            self._value = measurement
            self._initialized = True
        else:
            self._value = self.alpha * measurement + (1.0 - self.alpha) * self._value
        return self._value

    @property
    def value(self) -> float:
        return self._value


class LowPassFilter3D:
    """Three independent low-pass filters for (x, y, z) vectors."""

    def __init__(self, alpha: float = 0.1):
        self._fx = LowPassFilter(alpha)
        self._fy = LowPassFilter(alpha)
        self._fz = LowPassFilter(alpha)

    def update(self, x: float, y: float, z: float) -> tuple:
        return self._fx.update(x), self._fy.update(y), self._fz.update(z)

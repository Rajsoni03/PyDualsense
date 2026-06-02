"""Analog stick helpers."""

from ..protocol.input_report import StickState


def normalise(stick: StickState) -> tuple:
    """Return (x, y) each in −1.0 … +1.0."""
    return ((stick.x - 128) / 128.0, (stick.y - 128) / 128.0)

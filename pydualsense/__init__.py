"""
PyDualsense — PS5 DualSense controller library for Python.

Quick start::

    from pydualsense import DualSense

    ds = DualSense()
    ds.connect()
    state = ds.read()
    print(state.left_stick, state.buttons.cross)
    ds.set_led(0, 0, 255)
    ds.set_rumble(100, 100)
    ds.disconnect()
"""

from .controller import DualSense
from .protocol.constants import TriggerMode, PlayerLED, MicLED, DPadDirection
from .protocol.input_report import InputState

__all__ = ["DualSense", "TriggerMode", "PlayerLED", "MicLED", "DPadDirection", "InputState"]
__version__ = "0.1.0"

"""
Button state with edge-detection helpers.
"""

from ..protocol.input_report import ButtonState as _ButtonState


class ButtonState(_ButtonState):
    """Extends the dataclass with pressed/released edge detection."""
    pass


class ButtonTracker:
    """Tracks button state across frames and emits pressed/released events."""

    def __init__(self):
        self._prev: _ButtonState = _ButtonState()
        self._callbacks_pressed = {}
        self._callbacks_released = {}

    def update(self, current: _ButtonState):
        for name in vars(current):
            was = getattr(self._prev, name)
            now = getattr(current, name)
            if not was and now:
                for cb in self._callbacks_pressed.get(name, []):
                    cb(name)
            elif was and not now:
                for cb in self._callbacks_released.get(name, []):
                    cb(name)
        self._prev = current

    def on_press(self, button: str, callback):
        self._callbacks_pressed.setdefault(button, []).append(callback)

    def on_release(self, button: str, callback):
        self._callbacks_released.setdefault(button, []).append(callback)

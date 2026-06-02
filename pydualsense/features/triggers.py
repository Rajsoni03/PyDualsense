"""
High-level adaptive trigger effect builder used by DualSense.

These functions are convenience wrappers around OutputReport's trigger methods.
They return a (side, method_name, kwargs) tuple that the controller dispatches.
"""

from ..protocol.constants import TriggerMode


class TriggerEffect:
    """Describes a single adaptive trigger effect ready to be applied."""

    def __init__(self, mode: TriggerMode, params: dict):
        self.mode = mode
        self.params = params

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def off(cls) -> "TriggerEffect":
        return cls(TriggerMode.OFF, {})

    @classmethod
    def feedback(cls, start: int = 0, force: int = 128) -> "TriggerEffect":
        """Resistive feedback beginning at *start* with *force* (0–255 each)."""
        return cls(TriggerMode.FEEDBACK, {"start": start, "force": force})

    @classmethod
    def weapon(cls, start: int = 50, end: int = 100,
               force: int = 200) -> "TriggerEffect":
        """Simulates pulling a trigger: click at *start*, rigid to *end*."""
        return cls(TriggerMode.WEAPON, {"start": start, "end": end, "force": force})

    @classmethod
    def vibration(cls, position: int = 0, amplitude: int = 128,
                  frequency: int = 25) -> "TriggerEffect":
        """Vibrating effect at *position* with *amplitude* and *frequency* Hz."""
        return cls(TriggerMode.VIBRATION,
                   {"position": position, "amplitude": amplitude,
                    "frequency": frequency})

    @classmethod
    def slope(cls, start: int = 0, end: int = 255,
              start_force: int = 0, end_force: int = 255) -> "TriggerEffect":
        """Linearly increasing resistance from *start* to *end*."""
        return cls(TriggerMode.SLOPE_FEEDBACK,
                   {"start": start, "end": end,
                    "start_force": start_force, "end_force": end_force})

    @classmethod
    def rigid(cls) -> "TriggerEffect":
        """Maximum constant resistance regardless of position."""
        return cls(TriggerMode.RIGID, {})

    @classmethod
    def multi_pos(cls, positions: list, forces: list) -> "TriggerEffect":
        """Resistance zones at up to three discrete positions."""
        return cls(TriggerMode.MULTI_POS,
                   {"positions": positions, "forces": forces})

    def __repr__(self) -> str:
        return f"TriggerEffect({self.mode.name}, {self.params})"

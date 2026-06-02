"""Battery state re-export."""

from ..protocol.input_report import BatteryState
from ..protocol.constants import BatteryStatus

__all__ = ["BatteryState", "BatteryStatus"]

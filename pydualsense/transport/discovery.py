"""
Device enumeration helpers.
"""

from dataclasses import dataclass
from typing import List, Optional

try:
    import hid
except ImportError:
    hid = None  # type: ignore

from ..protocol.constants import DUALSENSE_VID, SUPPORTED_PIDS


@dataclass
class ControllerInfo:
    path: bytes
    vendor_id: int
    product_id: int
    serial_number: str
    manufacturer: str
    product: str
    interface: int

    def __str__(self) -> str:
        return (
            f"DualSense [{self.manufacturer} {self.product}] "
            f"VID={self.vendor_id:#06x} PID={self.product_id:#06x} "
            f"serial={self.serial_number!r}"
        )


def list_controllers() -> List[ControllerInfo]:
    """Return all connected DualSense controllers visible via hidapi."""
    if hid is None:
        raise RuntimeError("The 'hid' package is not installed.  Run: pip install hid")

    results: List[ControllerInfo] = []
    for dev in hid.enumerate():
        if dev["vendor_id"] == DUALSENSE_VID and dev["product_id"] in SUPPORTED_PIDS:
            results.append(ControllerInfo(
                path=dev["path"],
                vendor_id=dev["vendor_id"],
                product_id=dev["product_id"],
                serial_number=dev.get("serial_number", ""),
                manufacturer=dev.get("manufacturer_string", ""),
                product=dev.get("product_string", ""),
                interface=dev.get("interface_number", -1),
            ))
    return results


def find_controller(serial: Optional[str] = None) -> Optional[ControllerInfo]:
    """Return the first matching controller, optionally filtered by serial."""
    for c in list_controllers():
        if serial is None or c.serial_number == serial:
            return c
    return None

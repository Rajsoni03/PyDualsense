"""
Cross-platform HID transport using the `hid` (hidapi) library.

Works over both Bluetooth and USB — hidapi abstracts the difference.
On Linux, ensure the user has read/write access to the hidraw device:

    echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", MODE="0666"' \\
        | sudo tee /etc/udev/rules.d/70-dualsense.rules
    sudo udevadm trigger

On Windows, the controller must NOT have the default HID driver replaced
(no ViGEmBus needed for raw access; standard HID works with hidapi).
"""

from typing import Optional

try:
    import hid
except ImportError:
    hid = None  # type: ignore

from .base import Transport
from ..protocol.constants import (
    DUALSENSE_VID, SUPPORTED_PIDS,
    BT_INPUT_REPORT_LEN, USB_INPUT_REPORT_LEN,
    BT_INPUT_REPORT_ID, USB_INPUT_REPORT_ID,
)


class HIDTransport(Transport):
    """hidapi-backed HID transport for DualSense (BT + USB)."""

    def __init__(self):
        if hid is None:
            raise RuntimeError("The 'hid' package is not installed.  Run: pip install hid")
        self._device: Optional[hid.Device] = None
        self._is_bt: bool = False

    # ── Transport ABC ─────────────────────────────────────────────────────────

    def open(self, vendor_id: int = DUALSENSE_VID,
             product_id: int = SUPPORTED_PIDS[0]) -> None:
        """Open a DualSense device by VID/PID.

        Raises:
            RuntimeError: if no matching device is found.
            OSError: if hidapi cannot open the device (permissions, etc.).
        """
        self._device = hid.Device(vid=vendor_id, pid=product_id)
        self._device.nonblocking = False
        self._detect_connection_type()

    def open_path(self, path: bytes) -> None:
        """Open device by the exact hidraw path returned by :func:`list_controllers`."""
        self._device = hid.Device(path=path)
        self._device.nonblocking = False
        self._detect_connection_type()

    def close(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    def read(self, size: int = BT_INPUT_REPORT_LEN, timeout_ms: int = 100) -> bytes:
        if self._device is None:
            raise RuntimeError("Device not open")
        raw = self._device.read(size, timeout_ms)
        return bytes(raw) if raw else b""

    def write(self, data: bytes) -> int:
        if self._device is None:
            raise RuntimeError("Device not open")
        # hidapi on Linux/BT requires a leading zero byte as the report ID
        # if the OS doesn't add it automatically.  We always include it.
        return self._device.write(data)

    def send_feature_report(self, report_id: int, data: bytes) -> None:
        """Send a HID feature report.

        Args:
            report_id: The 1-byte feature report ID (e.g. 0x80).
            data:      Payload bytes (NOT including the report ID — hidapi
                       prepends it automatically when passed as data[0]).
        """
        if self._device is None:
            raise RuntimeError("Device not open")
        # hidapi send_feature_report expects the report ID as the first byte.
        self._device.send_feature_report(bytes([report_id]) + data)

    @property
    def is_open(self) -> bool:
        return self._device is not None

    # ── Connection-type detection ─────────────────────────────────────────────

    @property
    def is_bluetooth(self) -> bool:
        return self._is_bt

    def _detect_connection_type(self) -> None:
        """Probe the connection type by reading one report and checking its ID."""
        if self._device is None:
            return
        try:
            probe = self._device.read(BT_INPUT_REPORT_LEN, 500)
            if probe:
                self._is_bt = (probe[0] == BT_INPUT_REPORT_ID)
            else:
                # Default to BT (most common wireless usage)
                self._is_bt = True
        except Exception:
            self._is_bt = True

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

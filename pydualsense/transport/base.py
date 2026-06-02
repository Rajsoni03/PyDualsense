"""Abstract transport interface."""

from abc import ABC, abstractmethod


class Transport(ABC):
    """Base class for HID transport implementations."""

    @abstractmethod
    def open(self, vendor_id: int, product_id: int) -> None:
        """Open the HID device."""

    @abstractmethod
    def close(self) -> None:
        """Close the HID device."""

    @abstractmethod
    def read(self, size: int, timeout_ms: int = 100) -> bytes:
        """Read up to *size* bytes.  Returns empty bytes on timeout."""

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write *data* to the device.  Returns number of bytes written."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """True if the device is currently open."""

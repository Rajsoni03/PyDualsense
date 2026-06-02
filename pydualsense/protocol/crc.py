"""
CRC-32 helper for DualSense Bluetooth output reports.

The DualSense BT output protocol requires a CRC-32 checksum appended to every
output report.  The checksum is calculated over:

    bytes([0xA2]) + report_bytes[0:74]

using the standard (ISO 3309) CRC-32 polynomial (0x04C11DB7), then packed
as a little-endian uint32 into bytes 74–77 of the 78-byte output report.
"""

import binascii
import struct

from .constants import BT_OUTPUT_CRC_SEED


def crc32_bt(report: bytes) -> bytes:
    """Return the 4-byte little-endian CRC-32 for a BT output report payload.

    Args:
        report: First 74 bytes of the output report (before the CRC field).

    Returns:
        4-byte ``bytes`` object to be appended as bytes 74–77.
    """
    seed = bytes([BT_OUTPUT_CRC_SEED])
    checksum = binascii.crc32(seed + report[:74]) & 0xFFFFFFFF
    return struct.pack("<I", checksum)


def append_crc(report: bytearray) -> None:
    """Compute and write the CRC-32 into bytes 74–77 of *report* in place.

    Args:
        report: 78-byte bytearray to be mutated.
    """
    crc = crc32_bt(bytes(report))
    report[74:78] = crc

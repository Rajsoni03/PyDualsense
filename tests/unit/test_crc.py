"""Unit tests for CRC-32 BT output report calculation."""

import struct
import pytest
from pydualsense.protocol.crc import crc32_bt, append_crc
from pydualsense.protocol.constants import BT_OUTPUT_REPORT_LEN, BT_OUTPUT_CRC_SEED


def _make_report(**kwargs) -> bytearray:
    """Return a zeroed 78-byte output report buffer with correct header."""
    buf = bytearray(BT_OUTPUT_REPORT_LEN)
    buf[0] = 0x31   # report ID
    buf[1] = 0x00   # seq byte (0 for first packet)
    buf[2] = 0x10   # tag
    for k, v in kwargs.items():
        buf[int(k)] = v
    return buf


class TestCrc32Bt:
    def test_returns_4_bytes(self):
        report = bytes(74)
        result = crc32_bt(report)
        assert len(result) == 4

    def test_all_zeros_is_deterministic(self):
        r1 = crc32_bt(bytes(74))
        r2 = crc32_bt(bytes(74))
        assert r1 == r2

    def test_different_payloads_differ(self):
        r1 = crc32_bt(bytes(74))
        payload = bytearray(74)
        payload[4] = 0xFF           # change motor byte
        r2 = crc32_bt(bytes(payload))
        assert r1 != r2

    def test_known_value(self):
        # The seed byte 0xA2 prepended to 74 zero bytes:
        # binascii.crc32(b'\xa2' + bytes(74)) = 0xF4B8A8E6 (little-endian: E6 A8 B8 F4)
        import binascii
        expected = binascii.crc32(bytes([BT_OUTPUT_CRC_SEED]) + bytes(74)) & 0xFFFFFFFF
        result = struct.unpack("<I", crc32_bt(bytes(74)))[0]
        assert result == expected

    def test_seed_byte_affects_result(self):
        # Verify the seed byte (0xA2) is included in the computation
        import binascii
        without_seed = binascii.crc32(bytes(74)) & 0xFFFFFFFF
        with_seed    = struct.unpack("<I", crc32_bt(bytes(74)))[0]
        assert with_seed != without_seed


class TestAppendCrc:
    def test_modifies_bytes_74_77(self):
        buf = _make_report()
        buf[74:78] = b"\x00\x00\x00\x00"
        append_crc(buf)
        assert buf[74:78] != b"\x00\x00\x00\x00"

    def test_idempotent_content(self):
        buf1 = _make_report()
        buf2 = _make_report()
        append_crc(buf1)
        append_crc(buf2)
        assert buf1[74:78] == buf2[74:78]

    def test_consistent_with_crc32_bt(self):
        buf = _make_report()
        append_crc(buf)
        expected = crc32_bt(bytes(buf))
        assert buf[74:78] == expected

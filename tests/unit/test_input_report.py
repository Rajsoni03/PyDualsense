"""Unit tests for BT input report parsing."""

import struct
import pytest

from pydualsense.protocol.input_report import parse_bt, parse_input_report, InputState
from pydualsense.protocol.constants import DPadDirection, BT_INPUT_REPORT_ID


def _make_bt_report(fields: dict = None) -> bytes:
    """Build a minimal 78-byte BT input report with specific byte values.

    Pass a dict mapping integer byte offsets to values, e.g.::

        _make_bt_report({9: 0x20})   # cross button set
    """
    buf = bytearray(78)
    buf[0] = BT_INPUT_REPORT_ID   # 0x31
    buf[1] = 0x00                 # reserved
    # Defaults: sticks centred at 128
    buf[2] = 128   # left X
    buf[3] = 128   # left Y
    buf[4] = 128   # right X
    buf[5] = 128   # right Y
    for offset, value in (fields or {}).items():
        buf[int(offset)] = int(value)
    return bytes(buf)


class TestParseBtReportId:
    def test_wrong_report_id_raises(self):
        buf = bytearray(78)
        buf[0] = 0x01   # USB report ID, not BT
        with pytest.raises(ValueError, match="report ID"):
            parse_bt(bytes(buf))

    def test_short_report_raises(self):
        with pytest.raises(ValueError, match="too short"):
            parse_bt(bytes(10))

    def test_valid_report_id_accepted(self):
        state = parse_bt(_make_bt_report())
        assert isinstance(state, InputState)


class TestParseSticks:
    def test_centre_position(self):
        state = parse_bt(_make_bt_report())
        assert state.left_stick.x == 128
        assert state.left_stick.y == 128
        assert state.right_stick.x == 128
        assert state.right_stick.y == 128

    def test_left_stick_extremes(self):
        state = parse_bt(_make_bt_report({2: 0, 3: 255}))
        assert state.left_stick.x == 0
        assert state.left_stick.y == 255

    def test_right_stick_extremes(self):
        state = parse_bt(_make_bt_report({4: 255, 5: 0}))
        assert state.right_stick.x == 255
        assert state.right_stick.y == 0


class TestParseTriggers:
    def test_default_triggers_zero(self):
        state = parse_bt(_make_bt_report())
        assert state.l2 == 0
        assert state.r2 == 0

    def test_triggers_full(self):
        state = parse_bt(_make_bt_report({6: 255, 7: 255}))
        assert state.l2 == 255
        assert state.r2 == 255


class TestParseButtons:
    def test_no_buttons_pressed(self):
        state = parse_bt(_make_bt_report())
        assert not state.buttons.cross
        assert not state.buttons.ps

    def test_cross_button(self):
        # Buttons[0] at byte 9 (offset o+7 = 2+7 = 9): cross = bit 5
        state = parse_bt(_make_bt_report({9: 0x20}))
        assert state.buttons.cross
        assert not state.buttons.circle

    def test_triangle_button(self):
        state = parse_bt(_make_bt_report({9: 0x80}))
        assert state.buttons.triangle

    def test_l1_r1(self):
        # Buttons[1] at byte 10: L1=bit0, R1=bit1
        state = parse_bt(_make_bt_report({10: 0x03}))
        assert state.buttons.l1
        assert state.buttons.r1

    def test_ps_button(self):
        # Buttons[2] at byte 11: PS=bit0
        state = parse_bt(_make_bt_report({11: 0x01}))
        assert state.buttons.ps

    def test_touchpad_click(self):
        state = parse_bt(_make_bt_report({11: 0x02}))
        assert state.buttons.touchpad_click

    def test_mute_button(self):
        state = parse_bt(_make_bt_report({11: 0x04}))
        assert state.buttons.mute


class TestParseDPad:
    @pytest.mark.parametrize("val,expected", [
        (0, DPadDirection.N),
        (1, DPadDirection.NE),
        (2, DPadDirection.E),
        (4, DPadDirection.S),
        (6, DPadDirection.W),
        (8, DPadDirection.NEUTRAL),
        (9, DPadDirection.NEUTRAL),  # invalid → neutral
    ])
    def test_dpad_directions(self, val, expected):
        state = parse_bt(_make_bt_report({9: val & 0x0F}))
        assert state.dpad == expected


class TestParseGyroAccel:
    def test_zero_gyro(self):
        state = parse_bt(_make_bt_report())
        assert state.gyro.x == 0
        assert state.gyro.y == 0
        assert state.gyro.z == 0

    def test_gyro_values(self):
        # Gyro at offset 17 (stick_offset=2 + 15), 3 × int16 LE
        buf = bytearray(_make_bt_report())
        struct.pack_into("<hhh", buf, 17, 1000, -500, 250)
        state = parse_bt(bytes(buf))
        assert state.gyro.x == 1000
        assert state.gyro.y == -500
        assert state.gyro.z == 250

    def test_accel_values(self):
        buf = bytearray(_make_bt_report())
        struct.pack_into("<hhh", buf, 23, -9000, 100, 200)
        state = parse_bt(bytes(buf))
        assert state.accel.x == -9000
        assert state.accel.y == 100
        assert state.accel.z == 200


class TestAutoDetect:
    def test_bt_report_auto_detected(self):
        state = parse_input_report(_make_bt_report())
        assert isinstance(state, InputState)

    def test_unknown_report_id_raises(self):
        buf = bytearray(78)
        buf[0] = 0xFF
        with pytest.raises(ValueError):
            parse_input_report(bytes(buf))

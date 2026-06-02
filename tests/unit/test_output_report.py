"""Unit tests for output report serialisation."""

import struct
import pytest

from pydualsense.protocol.output_report import OutputReport
from pydualsense.protocol.constants import (
    BT_OUTPUT_REPORT_LEN, BT_OUTPUT_REPORT_ID, BT_OUTPUT_TAG,
    FLAG0_COMPATIBLE_VIBRATION, FLAG0_TRIGGER_R_EFFECT, FLAG0_TRIGGER_L_EFFECT,
    TriggerMode,
)
from pydualsense.protocol.crc import crc32_bt


class TestOutputReportStructure:
    def test_report_length(self):
        out = OutputReport()
        data = out.build()
        assert len(data) == BT_OUTPUT_REPORT_LEN

    def test_report_id_and_tag(self):
        out = OutputReport()
        data = out.build()
        assert data[0] == BT_OUTPUT_REPORT_ID
        assert data[1] == BT_OUTPUT_TAG

    def test_crc32_is_valid(self):
        out = OutputReport()
        data = out.build()
        expected = crc32_bt(data)
        assert data[74:78] == expected


class TestRumble:
    def test_right_motor_set(self):
        out = OutputReport()
        out.set_rumble(200, 0)
        data = out.build()
        assert data[4] == 200
        assert data[5] == 0

    def test_left_motor_set(self):
        out = OutputReport()
        out.set_rumble(0, 150)
        data = out.build()
        assert data[4] == 0
        assert data[5] == 150

    def test_rumble_flag_set(self):
        out = OutputReport()
        out.set_rumble(100, 100)
        data = out.build()
        assert data[2] & FLAG0_COMPATIBLE_VIBRATION

    def test_rumble_clamped(self):
        out = OutputReport()
        out.set_rumble(999, -5)
        data = out.build()
        assert data[4] == 255
        assert data[5] == 0


class TestTriggerEffects:
    def test_right_trigger_off(self):
        out = OutputReport()
        out.set_trigger_off("right")
        data = out.build()
        assert data[18] == TriggerMode.OFF

    def test_left_trigger_off(self):
        out = OutputReport()
        out.set_trigger_off("left")
        data = out.build()
        assert data[27] == TriggerMode.OFF

    def test_right_trigger_feedback_mode(self):
        out = OutputReport()
        out.set_trigger_feedback("right", start=50, force=180)
        data = out.build()
        assert data[18] == TriggerMode.FEEDBACK
        assert data[19] == 50    # start
        assert data[20] == 180   # force

    def test_left_trigger_weapon_mode(self):
        out = OutputReport()
        out.set_trigger_weapon("left", start=30, end=100, force=200)
        data = out.build()
        assert data[27] == TriggerMode.WEAPON
        assert data[28] == 30    # start
        assert data[29] == 100   # end
        assert data[30] == 200   # force

    def test_vibration_mode(self):
        out = OutputReport()
        out.set_trigger_vibration("right", position=0, amplitude=200, frequency=30)
        data = out.build()
        assert data[18] == TriggerMode.VIBRATION
        assert data[20] == 200   # amplitude
        assert data[21] == 30    # frequency

    def test_rigid_mode(self):
        out = OutputReport()
        out.set_trigger_rigid("right")
        data = out.build()
        assert data[18] == TriggerMode.RIGID

    def test_trigger_flag_right(self):
        out = OutputReport()
        out.set_trigger_feedback("right", start=0, force=100)
        data = out.build()
        assert data[2] & FLAG0_TRIGGER_R_EFFECT

    def test_trigger_flag_left(self):
        out = OutputReport()
        out.set_trigger_feedback("left", start=0, force=100)
        data = out.build()
        assert data[2] & FLAG0_TRIGGER_L_EFFECT

    def test_invalid_side_raises(self):
        out = OutputReport()
        with pytest.raises(ValueError):
            out.set_trigger_off("invalid_side")


class TestLightBar:
    def test_rgb_bytes_set(self):
        out = OutputReport()
        out.set_lightbar(255, 128, 0)
        data = out.build()
        assert data[47] == 255
        assert data[48] == 128
        assert data[49] == 0

    def test_rgb_clamped(self):
        out = OutputReport()
        out.set_lightbar(300, -1, 500)
        data = out.build()
        assert data[47] == 255
        assert data[48] == 0
        assert data[49] == 255


class TestPlayerLeds:
    def test_player_leds_set(self):
        out = OutputReport()
        out.set_player_leds(0b00111)
        data = out.build()
        assert data[46] == 0b00111

    def test_player_leds_mask(self):
        out = OutputReport()
        out.set_player_leds(0xFF)   # all 8 bits, only low 5 should survive
        data = out.build()
        assert data[46] == 0x1F


class TestReset:
    def test_reset_clears_motors(self):
        out = OutputReport()
        out.set_rumble(255, 255)
        out.reset()
        data = out.build()
        assert data[4] == 0
        assert data[5] == 0

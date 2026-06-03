"""Unit tests for output report serialisation."""

import struct
import pytest

from pydualsense.protocol.output_report import OutputReport
from pydualsense.protocol.constants import (
    BT_OUTPUT_REPORT_LEN, BT_OUTPUT_REPORT_ID, BT_OUTPUT_TAG,
    FLAG0_COMPATIBLE_VIBRATION, FLAG0_TRIGGER_R_EFFECT, FLAG0_TRIGGER_L_EFFECT,
    FLAG1_LIGHTBAR_COLOR, FLAG1_PLAYER_LEDS,
    TriggerMode,
)
from pydualsense.protocol.crc import crc32_bt


class TestOutputReportStructure:
    def test_report_length(self):
        out = OutputReport()
        data = out.build()
        assert len(data) == BT_OUTPUT_REPORT_LEN

    def test_report_id(self):
        out = OutputReport()
        data = out.build()
        assert data[0] == BT_OUTPUT_REPORT_ID

    def test_tag_at_byte_2(self):
        """Tag 0x10 lives at buf[2]; buf[1] is the sequence byte."""
        out = OutputReport()
        data = out.build()
        assert data[2] == BT_OUTPUT_TAG

    def test_sequence_byte_increments(self):
        out = OutputReport()
        first  = out.build()[1]
        second = out.build()[1]
        assert first  == 0x00          # seq 0 → (0 & 0x0F) << 4 = 0x00
        assert second == 0x10          # seq 1 → (1 & 0x0F) << 4 = 0x10

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
        assert data[5] == 200
        assert data[6] == 0

    def test_left_motor_set(self):
        out = OutputReport()
        out.set_rumble(0, 150)
        data = out.build()
        assert data[5] == 0
        assert data[6] == 150

    def test_rumble_flag_set(self):
        out = OutputReport()
        out.set_rumble(100, 100)
        data = out.build()
        assert data[3] & FLAG0_COMPATIBLE_VIBRATION

    def test_rumble_clamped(self):
        out = OutputReport()
        out.set_rumble(999, -5)
        data = out.build()
        assert data[5] == 255
        assert data[6] == 0


class TestTriggerEffects:
    def test_right_trigger_off(self):
        out = OutputReport()
        out.set_trigger_off("right")
        data = out.build()
        assert data[13] == TriggerMode.OFF

    def test_left_trigger_off(self):
        out = OutputReport()
        out.set_trigger_off("left")
        data = out.build()
        assert data[24] == TriggerMode.OFF

    def test_right_trigger_feedback_mode(self):
        out = OutputReport()
        out.set_trigger_feedback("right", start=50, force=180)
        data = out.build()
        assert data[13] == TriggerMode.FEEDBACK
        assert data[14] == 50    # start  (param0)
        assert data[15] == 180   # force  (param1)

    def test_left_trigger_weapon_mode(self):
        out = OutputReport()
        out.set_trigger_weapon("left", start=30, end=100, force=200)
        data = out.build()
        assert data[24] == TriggerMode.WEAPON
        assert data[25] == 30    # start  (param0)
        assert data[26] == 100   # end    (param1)
        assert data[27] == 200   # force  (param2)

    def test_vibration_mode(self):
        out = OutputReport()
        out.set_trigger_vibration("right", position=0, amplitude=200, frequency=30)
        data = out.build()
        assert data[13] == TriggerMode.VIBRATION   # 0x06  Simple_Vibration
        assert data[14] == 30    # frequency  (param0 in Simple_Vibration layout)
        assert data[15] == 200   # amplitude  (param1)
        assert data[16] == 0     # position   (param2)

    def test_rigid_mode(self):
        out = OutputReport()
        out.set_trigger_rigid("right")
        data = out.build()
        # Rigid is implemented as Simple_Feedback (0x01) at position 0, full force.
        assert data[13] == TriggerMode.FEEDBACK   # 0x01
        assert data[14] == 0    # position = start of trigger travel
        assert data[15] == 255  # maximum force

    def test_trigger_block_is_11_bytes(self):
        """Each trigger occupies exactly 11 bytes; left trigger starts at byte 24."""
        out = OutputReport()
        out.set_trigger_feedback("right", start=1, force=2)
        out.set_trigger_feedback("left",  start=3, force=4)
        data = out.build()
        assert data[13] == TriggerMode.FEEDBACK   # right mode
        assert data[14] == 1                       # right param0
        assert data[24] == TriggerMode.FEEDBACK   # left mode (11 bytes after 13)
        assert data[25] == 3                       # left param0

    def test_trigger_flag_right(self):
        out = OutputReport()
        out.set_trigger_feedback("right", start=0, force=100)
        data = out.build()
        assert data[3] & FLAG0_TRIGGER_R_EFFECT

    def test_trigger_flag_left(self):
        out = OutputReport()
        out.set_trigger_feedback("left", start=0, force=100)
        data = out.build()
        assert data[3] & FLAG0_TRIGGER_L_EFFECT

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

    def test_lightbar_flag_set(self):
        out = OutputReport()
        out.set_lightbar(0, 0, 255)
        data = out.build()
        assert data[4] & FLAG1_LIGHTBAR_COLOR

    def test_lightbar_default_bit_clear(self):
        """Bit 3 of validFlag1 must be 0 when setting custom colour."""
        out = OutputReport()
        out.set_lightbar(255, 0, 0)
        data = out.build()
        assert not (data[4] & 0x08)


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

    def test_player_leds_flag_set(self):
        out = OutputReport()
        out.set_player_leds(0x04)
        data = out.build()
        assert data[4] & FLAG1_PLAYER_LEDS


class TestReset:
    def test_reset_clears_motors(self):
        out = OutputReport()
        out.set_rumble(255, 255)
        out.reset()
        data = out.build()
        assert data[5] == 0
        assert data[6] == 0

    def test_reset_clears_lightbar(self):
        out = OutputReport()
        out.set_lightbar(255, 0, 0)
        out.reset()
        data = out.build()
        assert not (data[4] & FLAG1_LIGHTBAR_COLOR)

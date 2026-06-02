"""
Build DualSense HID output reports.

Bluetooth output report layout (0x31, 78 bytes)
────────────────────────────────────────────────
 0    Report ID (0x31)
 1    Tag        (0x10)
 2    valid_flag0   — which groups to update
 3    valid_flag1
 4    motor_right   — right (small) rumble motor, 0–255
 5    motor_left    — left  (large) rumble motor, 0–255
 6–9  Reserved
10    headphone_audio_enable
11    headphone_volume         (0–0x7F)
12    speaker_audio_enable
13    speaker_volume           (0–0x7F)
14    microphone_volume        (0–0x7F)
15    audio_enable_bits
16    mic_select
17    audio_mute
18    right trigger mode       ──┐ 9 bytes
19–26 right trigger params    ──┘
27    left trigger mode        ──┐ 9 bytes
28–35 left trigger params     ──┘
36–40 Reserved (5 bytes)
41    valid_flag2
42–43 Reserved (2 bytes)
44    lightbar_setup           (0x01=custom RGB, 0x02=release)
45    led_brightness           (0x00=high, 0x01=mid, 0x02=low)
46    player_leds              (bitmask: bits 0–4 = LED 1–5)
47    lightbar_red
48    lightbar_green
49    lightbar_blue
50–73 Reserved / padding
74–77 CRC-32 (appended by send path)
"""

from dataclasses import dataclass, field
from typing import List

from .constants import (
    BT_OUTPUT_REPORT_ID, BT_OUTPUT_TAG, BT_OUTPUT_REPORT_LEN,
    TriggerMode,
    FLAG0_COMPATIBLE_VIBRATION, FLAG0_TRIGGER_R_EFFECT, FLAG0_TRIGGER_L_EFFECT,
    FLAG1_MIC_MUTE_LED,
    FLAG2_LIGHTBAR, FLAG2_LED_BRIGHTNESS, FLAG2_PLAYER_LEDS,
    LIGHTBAR_CUSTOM_COLOR,
    MicLED, PlayerLED,
)
from .crc import append_crc


# ── Trigger effect builder ────────────────────────────────────────────────────

def _build_trigger_off() -> bytes:
    return bytes(9)


def _build_trigger_feedback(start: int, force: int) -> bytes:
    """Resistive feedback from *start* position with *force* strength."""
    p = bytearray(9)
    p[0] = TriggerMode.FEEDBACK
    p[1] = max(0, min(255, start))
    p[2] = max(0, min(255, force))
    return bytes(p)


def _build_trigger_weapon(start: int, end: int, force: int) -> bytes:
    """Click/snap at *start*, rigid up to *end*, with *force*."""
    p = bytearray(9)
    p[0] = TriggerMode.WEAPON
    p[1] = max(0, min(255, start))
    p[2] = max(0, min(255, end))
    p[3] = max(0, min(255, force))
    return bytes(p)


def _build_trigger_vibration(position: int, amplitude: int, frequency: int) -> bytes:
    """Vibrating effect at *position* with *amplitude* and *frequency* (Hz)."""
    p = bytearray(9)
    p[0] = TriggerMode.VIBRATION
    p[1] = max(0, min(255, position))
    p[2] = max(0, min(255, amplitude))
    p[3] = max(0, min(255, frequency))
    return bytes(p)


def _build_trigger_slope(start: int, end: int, start_force: int, end_force: int) -> bytes:
    """Linearly increasing resistance from *start* to *end*."""
    p = bytearray(9)
    p[0] = TriggerMode.SLOPE_FEEDBACK
    p[1] = max(0, min(255, start))
    p[2] = max(0, min(255, end))
    p[3] = max(0, min(255, start_force))
    p[4] = max(0, min(255, end_force))
    return bytes(p)


def _build_trigger_rigid() -> bytes:
    """Maximum constant resistance."""
    p = bytearray(9)
    p[0] = TriggerMode.RIGID
    return bytes(p)


def _build_trigger_multi_pos(positions: List[int], forces: List[int]) -> bytes:
    """Resistance at up to 3 discrete positions."""
    p = bytearray(9)
    p[0] = TriggerMode.MULTI_POS
    for i, (pos, force) in enumerate(zip(positions[:3], forces[:3])):
        p[1 + i * 2] = max(0, min(255, pos))
        p[2 + i * 2] = max(0, min(255, force))
    return bytes(p)


# ── Output report class ───────────────────────────────────────────────────────

class OutputReport:
    """Mutable output-report state.  Call :meth:`build` to serialise."""

    def __init__(self):
        self._buf = bytearray(BT_OUTPUT_REPORT_LEN)
        self._buf[0] = BT_OUTPUT_REPORT_ID
        self._buf[1] = BT_OUTPUT_TAG

        # Default: custom lightbar colour enabled
        self._buf[41] = FLAG2_LIGHTBAR | FLAG2_PLAYER_LEDS | FLAG2_LED_BRIGHTNESS
        self._buf[44] = LIGHTBAR_CUSTOM_COLOR
        self._buf[45] = 0x00  # high brightness

        # Track which flag0 features are active
        self._flag0: int = 0
        self._flag1: int = 0

    # ── Rumble ────────────────────────────────────────────────────────────────

    def set_rumble(self, right: int, left: int) -> None:
        """Set ERM rumble motors.  right = small (HF), left = large (LF), 0–255."""
        self._buf[4] = max(0, min(255, right))
        self._buf[5] = max(0, min(255, left))
        self._flag0 |= FLAG0_COMPATIBLE_VIBRATION

    # ── Adaptive triggers ─────────────────────────────────────────────────────

    def set_trigger_off(self, side: str) -> None:
        self._set_trigger(side, _build_trigger_off())

    def set_trigger_feedback(self, side: str, start: int = 0, force: int = 128) -> None:
        self._set_trigger(side, _build_trigger_feedback(start, force))

    def set_trigger_weapon(self, side: str, start: int = 0,
                           end: int = 100, force: int = 200) -> None:
        self._set_trigger(side, _build_trigger_weapon(start, end, force))

    def set_trigger_vibration(self, side: str, position: int = 0,
                               amplitude: int = 128, frequency: int = 25) -> None:
        self._set_trigger(side, _build_trigger_vibration(position, amplitude, frequency))

    def set_trigger_slope(self, side: str, start: int = 0, end: int = 255,
                          start_force: int = 0, end_force: int = 255) -> None:
        self._set_trigger(side, _build_trigger_slope(start, end, start_force, end_force))

    def set_trigger_rigid(self, side: str) -> None:
        self._set_trigger(side, _build_trigger_rigid())

    def set_trigger_multi_pos(self, side: str, positions: List[int],
                               forces: List[int]) -> None:
        self._set_trigger(side, _build_trigger_multi_pos(positions, forces))

    def _set_trigger(self, side: str, effect: bytes) -> None:
        side = side.lower()
        if side in ("right", "r", "r2"):
            self._buf[18:27] = effect
            self._flag0 |= FLAG0_TRIGGER_R_EFFECT
        elif side in ("left", "l", "l2"):
            self._buf[27:36] = effect
            self._flag0 |= FLAG0_TRIGGER_L_EFFECT
        else:
            raise ValueError(f"side must be 'left' or 'right', got {side!r}")

    # ── Light bar RGB ─────────────────────────────────────────────────────────

    def set_lightbar(self, r: int, g: int, b: int) -> None:
        """Set RGB light-bar colour (each 0–255)."""
        self._buf[47] = max(0, min(255, r))
        self._buf[48] = max(0, min(255, g))
        self._buf[49] = max(0, min(255, b))
        self._buf[44] = LIGHTBAR_CUSTOM_COLOR
        self._buf[41] |= FLAG2_LIGHTBAR

    # ── Player indicator LEDs ─────────────────────────────────────────────────

    def set_player_leds(self, mask: int) -> None:
        """Set player-indicator LED bitmask (bits 0–4 = LED 1–5)."""
        self._buf[46] = mask & 0x1F
        self._buf[41] |= FLAG2_PLAYER_LEDS

    # ── Microphone mute LED ───────────────────────────────────────────────────

    def set_mic_led(self, mode: MicLED) -> None:
        self._buf[35] = int(mode)    # mute LED is in reserved section after trigger effects
        self._flag1 |= FLAG1_MIC_MUTE_LED

    # ── Audio ─────────────────────────────────────────────────────────────────

    def set_speaker_volume(self, volume: int) -> None:
        """Set built-in speaker volume (0–0x7F)."""
        self._buf[13] = max(0, min(0x7F, volume))
        self._buf[12] = 0x01   # speaker_audio_enable

    def set_mic_volume(self, volume: int) -> None:
        """Set microphone volume (0–0x7F)."""
        self._buf[14] = max(0, min(0x7F, volume))

    def set_headphone_volume(self, volume: int) -> None:
        """Set headphone volume (0–0x7F)."""
        self._buf[11] = max(0, min(0x7F, volume))
        self._buf[10] = 0x01   # headphone_audio_enable

    # ── Serialise ─────────────────────────────────────────────────────────────

    def build(self) -> bytes:
        """Return the 78-byte BT output report with CRC-32 appended."""
        self._buf[2] = self._flag0 & 0xFF
        self._buf[3] = self._flag1 & 0xFF
        append_crc(self._buf)
        return bytes(self._buf)

    def reset(self) -> None:
        """Clear all pending changes back to a neutral state."""
        self.__init__()

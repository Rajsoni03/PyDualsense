"""
Build DualSense HID output reports.

Bluetooth output report layout (78 bytes, written via hidapi device.write())
─────────────────────────────────────────────────────────────────────────────
 0    Report ID   (0x31)
 1    Sequence    (seq & 0x0F) << 4  – rolling 0-15
 2    Tag         0x10
 3    valid_flag0  – which feature groups to update
 4    valid_flag1
 5    motor_right  – right (small/HF) ERM motor, 0–255
 6    motor_left   – left  (large/LF) ERM motor, 0–255
 7    headphone_volume     (0–0x7F)
 8    speaker_volume       (0–0x7F)
 9    mic_volume           (0–0x7F)
10    audio_control
11    mute_led_control
12    power_save_mute_control
13    right trigger mode        ──┐ 11 bytes (mode + 10 params)
14–23 right trigger params 0–9 ──┘
24    left trigger mode         ──┐ 11 bytes
25–34 left trigger params 0–9  ──┘
35–38 Reserved (4 bytes)
39    haptic_volume
40    audio_control_2
41    valid_flag2
42–43 Reserved (2 bytes)
44    lightbar_setup
45    led_brightness        (0x00=high, 0x01=mid, 0x02=low)
46    player_leds           (bitmask: bits 0–4 = LED 1–5)
47    lightbar_red
48    lightbar_green
49    lightbar_blue
50–73 Reserved / padding (24 bytes)
74–77 CRC-32 (appended by build())
"""

from typing import List

from .constants import (
    BT_OUTPUT_REPORT_ID, BT_OUTPUT_TAG, BT_OUTPUT_REPORT_LEN,
    TriggerMode,
    FLAG0_COMPATIBLE_VIBRATION, FLAG0_TRIGGER_R_EFFECT, FLAG0_TRIGGER_L_EFFECT,
    FLAG0_HEADPHONE_VOLUME, FLAG0_SPEAKER_VOLUME, FLAG0_MIC_VOLUME,
    FLAG1_MIC_MUTE_LED, FLAG1_LIGHTBAR_COLOR, FLAG1_PLAYER_LEDS,
    FLAG2_LED_BRIGHTNESS,
    MicLED,
)
from .crc import append_crc


# ── Trigger effect builders (11 bytes each: 1 mode + 10 params) ───────────────

def _build_trigger_off() -> bytes:
    """Release trigger to neutral using the official Off mode byte (0x05)."""
    p = bytearray(11)
    p[0] = TriggerMode.OFF   # 0x05 — correct Off per Nielk1/Sony reference
    return bytes(p)


def _build_trigger_feedback(start: int, force: int) -> bytes:
    """Resistive feedback from *start* position with *force* strength."""
    p = bytearray(11)
    p[0] = TriggerMode.FEEDBACK   # 0x01  Simple_Feedback
    p[1] = max(0, min(255, start))
    p[2] = max(0, min(255, force))
    return bytes(p)


def _build_trigger_weapon(start: int, end: int, force: int) -> bytes:
    """Click/snap at *start*, rigid up to *end*, with *force*."""
    p = bytearray(11)
    p[0] = TriggerMode.WEAPON     # 0x02  Simple_Weapon
    p[1] = max(0, min(255, start))
    p[2] = max(0, min(255, end))
    p[3] = max(0, min(255, force))
    return bytes(p)


def _build_trigger_vibration(position: int, amplitude: int, frequency: int) -> bytes:
    """Vibrating effect using Simple_Vibration (0x06).

    Byte layout for mode 0x06: [mode, frequency, amplitude, position, 0…]
    """
    p = bytearray(11)
    p[0] = TriggerMode.VIBRATION  # 0x06  Simple_Vibration
    p[1] = max(0, min(255, frequency))   # param[0] = frequency
    p[2] = max(0, min(255, amplitude))   # param[1] = amplitude
    p[3] = max(0, min(255, position))    # param[2] = position
    return bytes(p)


def _pack_multi_position_feedback(strengths: List[int]) -> bytes:
    """Pack per-zone strength values into Official Feedback (0x21) format.

    strengths: list of up to 10 integers, each 0–8
                (0 = zone inactive, 1–8 = resistance level).

    The official mode uses bit-packing:
      active_zones: 10-bit mask (bit i = zone i active)
      force_zones:  30-bit value (3 bits per zone, value = strength−1)
    """
    p = bytearray(11)
    p[0] = TriggerMode.FEEDBACK_FULL   # 0x21
    force_zones  = 0
    active_zones = 0
    for i, s in enumerate(strengths[:10]):
        if s > 0:
            fv = (max(1, min(8, s)) - 1) & 0x07
            force_zones  |= fv << (3 * i)
            active_zones |= 1  << i
    p[1] = (active_zones >>  0) & 0xFF
    p[2] = (active_zones >>  8) & 0xFF
    p[3] = (force_zones  >>  0) & 0xFF
    p[4] = (force_zones  >>  8) & 0xFF
    p[5] = (force_zones  >> 16) & 0xFF
    p[6] = (force_zones  >> 24) & 0xFF
    return bytes(p)


def _build_trigger_slope(start: int, end: int, start_force: int, end_force: int) -> bytes:
    """Linearly increasing resistance using the official bit-packed Feedback (0x21).

    Parameters are 0–255 and are mapped to the controller's zone/strength space:
      position 0–255 → zone 0–9 (0 = trigger at rest, 9 = full press)
      force    0–255 → strength 1–8
    """
    start_z = max(0, min(8, round(max(0, start)      * 8 / 255)))
    end_z   = max(start_z + 1, min(9, round(max(0, end)        * 9 / 255)))
    start_s = max(1, round(max(0, start_force) * 8 / 255)) if start_force else 1
    end_s   = max(1, min(8, round(max(0, end_force)   * 8 / 255)))

    strengths = [0] * 10
    span = end_z - start_z
    for i in range(10):
        if i < start_z:
            strengths[i] = 0
        elif i <= end_z:
            t = (i - start_z) / span
            strengths[i] = round(start_s + t * (end_s - start_s))
        else:
            strengths[i] = end_s
    return _pack_multi_position_feedback(strengths)


def _build_trigger_rigid() -> bytes:
    """Maximum constant resistance via Simple_Feedback at position 0, full strength."""
    p = bytearray(11)
    p[0] = TriggerMode.FEEDBACK   # 0x01  Simple_Feedback
    p[1] = 0    # position = start of trigger travel
    p[2] = 255  # maximum force
    return bytes(p)


def _build_trigger_multi_pos(positions: List[int], forces: List[int]) -> bytes:
    """Resistance at discrete positions using the official bit-packed Feedback (0x21).

    positions / forces are 0–255 each; they are mapped to zone/strength space.
    Up to 10 (position, force) pairs; later pairs overwrite earlier ones at
    the same zone.
    """
    strengths = [0] * 10
    for pos, force in zip(positions, forces):
        if force > 0:
            zone = max(0, min(9, round(max(0, pos) * 9 / 255)))
            s    = max(1, min(8, round(max(0, force) * 8 / 255)))
            strengths[zone] = max(strengths[zone], s)
    return _pack_multi_position_feedback(strengths)


# ── Output report class ───────────────────────────────────────────────────────

class OutputReport:
    """Mutable output-report state.  Call :meth:`build` to serialise."""

    def __init__(self):
        self._buf = bytearray(BT_OUTPUT_REPORT_LEN)
        self._buf[0] = BT_OUTPUT_REPORT_ID   # 0x31
        # buf[1] = seq tag — written in build()
        self._buf[2] = BT_OUTPUT_TAG          # 0x10
        self._buf[45] = 0x00                  # LED brightness: high

        self._flag0: int = 0
        self._flag1: int = 0
        self._flag2: int = 0
        self._seq:   int = 0

    # ── Rumble ────────────────────────────────────────────────────────────────

    def set_rumble(self, right: int, left: int) -> None:
        """Set ERM rumble motors.  right = small (HF), left = large (LF), 0–255."""
        self._buf[5] = max(0, min(255, right))
        self._buf[6] = max(0, min(255, left))
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
            self._buf[13:24] = effect          # 11 bytes: right trigger
            self._flag0 |= FLAG0_TRIGGER_R_EFFECT
        elif side in ("left", "l", "l2"):
            self._buf[24:35] = effect          # 11 bytes: left trigger
            self._flag0 |= FLAG0_TRIGGER_L_EFFECT
        else:
            raise ValueError(f"side must be 'left' or 'right', got {side!r}")

    # ── Light bar RGB ─────────────────────────────────────────────────────────

    def set_lightbar(self, r: int, g: int, b: int) -> None:
        """Set RGB light-bar colour (each 0–255)."""
        self._buf[47] = max(0, min(255, r))
        self._buf[48] = max(0, min(255, g))
        self._buf[49] = max(0, min(255, b))
        # Enable custom colour; ensure bit 3 (default-release) is clear
        self._flag1 |= FLAG1_LIGHTBAR_COLOR
        self._flag1 &= ~0x08   # clear FLAG1_LIGHTBAR_DEFAULT (bit 3)

    # ── Player indicator LEDs ─────────────────────────────────────────────────

    def set_player_leds(self, mask: int) -> None:
        """Set player-indicator LED bitmask (bits 0–4 = LED 1–5)."""
        self._buf[46] = mask & 0x1F
        self._flag1 |= FLAG1_PLAYER_LEDS

    # ── LED brightness ────────────────────────────────────────────────────────

    def set_led_brightness(self, level: int) -> None:
        """Set LED brightness (0=high, 1=medium, 2=low)."""
        self._buf[45] = max(0, min(2, level))
        self._flag2 |= FLAG2_LED_BRIGHTNESS

    # ── Microphone mute LED ───────────────────────────────────────────────────

    def set_mic_led(self, mode: MicLED) -> None:
        self._buf[11] = int(mode)
        self._flag1 |= FLAG1_MIC_MUTE_LED

    # ── Audio ─────────────────────────────────────────────────────────────────

    def set_speaker_volume(self, volume: int) -> None:
        """Set built-in speaker volume (0–0x7F)."""
        self._buf[8] = max(0, min(0x7F, volume))
        self._flag0 |= FLAG0_SPEAKER_VOLUME

    def set_mic_volume(self, volume: int) -> None:
        """Set microphone volume (0–0x7F)."""
        self._buf[9] = max(0, min(0x7F, volume))
        self._flag0 |= FLAG0_MIC_VOLUME

    def set_headphone_volume(self, volume: int) -> None:
        """Set headphone volume (0–0x7F)."""
        self._buf[7] = max(0, min(0x7F, volume))
        self._flag0 |= FLAG0_HEADPHONE_VOLUME

    # ── Serialise ─────────────────────────────────────────────────────────────

    def build(self) -> bytes:
        """Return the 78-byte BT output report with CRC-32 appended."""
        self._buf[1]  = (self._seq & 0x0F) << 4
        self._seq     = (self._seq + 1) & 0x0F
        self._buf[3]  = self._flag0 & 0xFF
        self._buf[4]  = self._flag1 & 0xFF
        self._buf[41] = self._flag2 & 0xFF
        append_crc(self._buf)
        return bytes(self._buf)

    def reset(self) -> None:
        """Clear all pending changes back to a neutral state."""
        self.__init__()

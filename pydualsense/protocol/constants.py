"""
Enumerations and constants for the DualSense HID protocol.
"""

from enum import IntEnum, IntFlag


# ── Device identifiers ────────────────────────────────────────────────────────

DUALSENSE_VID = 0x054C          # Sony
DUALSENSE_PID_BT = 0x0CE6       # DualSense (Bluetooth)
DUALSENSE_PID_USB = 0x0CE6      # DualSense (USB) — same PID, different report
DUALSENSE_EDGE_PID_BT = 0x0DF2  # DualSense Edge (Bluetooth)
DUALSENSE_EDGE_PID_USB = 0x0DF2 # DualSense Edge (USB)

SUPPORTED_PIDS = (DUALSENSE_PID_BT, DUALSENSE_EDGE_PID_BT)

# ── Report IDs ────────────────────────────────────────────────────────────────

BT_INPUT_REPORT_ID = 0x31
BT_OUTPUT_REPORT_ID = 0x31
USB_INPUT_REPORT_ID = 0x01
USB_OUTPUT_REPORT_ID = 0x02

BT_INPUT_REPORT_LEN = 78
BT_OUTPUT_REPORT_LEN = 78
USB_INPUT_REPORT_LEN = 64

BT_OUTPUT_TAG = 0x10            # Second byte of BT output report
BT_OUTPUT_CRC_SEED = 0xA2       # Prepended byte for CRC32 calculation

# ── Output report flag bytes ──────────────────────────────────────────────────

# valid_flag0  (byte 2 of output report)
FLAG0_COMPATIBLE_VIBRATION = 0x01   # Enable ERM (classic rumble) motors
FLAG0_HAPTICS_SELECT       = 0x02   # 0 = ERM, 1 = HD haptics
FLAG0_TRIGGER_R_EFFECT     = 0x04   # Enable right (R2) trigger effect
FLAG0_TRIGGER_L_EFFECT     = 0x08   # Enable left  (L2) trigger effect
FLAG0_HEADPHONE_VOLUME     = 0x10   # Update headphone volume
FLAG0_SPEAKER_VOLUME       = 0x20   # Update speaker volume
FLAG0_MIC_VOLUME           = 0x40   # Update microphone volume
FLAG0_AUDIO_CONTROL        = 0x80   # Enable audio control fields

# valid_flag1  (byte 4 of output report)
# Bit 3 (0x08): when SET the controller returns to its default lightbar colour;
# when CLEAR the controller uses the RGB values supplied by the host.
FLAG1_MIC_MUTE_LED         = 0x01   # bit 0 – control mic-mute LED
FLAG1_POWER_SAVE           = 0x02   # bit 1 – power-save mode
FLAG1_LIGHTBAR_COLOR       = 0x04   # bit 2 – apply custom lightbar RGB
FLAG1_LIGHTBAR_DEFAULT     = 0x08   # bit 3 – release to default colour (set=default, clear=custom)
FLAG1_PLAYER_LEDS          = 0x10   # bit 4 – update player-indicator LEDs

# valid_flag2  (byte 41 of output report)
FLAG2_LED_BRIGHTNESS       = 0x01   # bit 0 – update LED brightness

# Lightbar setup byte  (byte 44 of output report)
LIGHTBAR_CUSTOM_COLOR = 0x00    # 0x00 = controlled by FLAG1_LIGHTBAR_COLOR / FLAG1_LIGHTBAR_DEFAULT
LIGHTBAR_RELEASE      = 0x02    # 0x02 = release / return to default

# ── Adaptive trigger modes ────────────────────────────────────────────────────

class TriggerMode(IntEnum):
    """Adaptive trigger effect modes.

    Hardware modes (0x01–0x26) are the actual bytes written to the trigger
    mode field.  Logical modes (0xFD–0xFF) are dispatch keys used only by
    TriggerEffect; the builder functions convert them to the correct hardware
    bytes internally.

    Simple modes (FEEDBACK / WEAPON / VIBRATION) use plain byte parameters and
    work reliably across all firmware versions.  FEEDBACK_FULL / WEAPON_FULL /
    VIBRATION_FULL are the official Sony bit-packed variants used for multi-zone
    effects.
    """
    # ── Hardware mode bytes (written to trigger block byte 0) ─────────────────
    OFF            = 0x05  # No effect; trigger returns to neutral position
    FEEDBACK       = 0x01  # Simple_Feedback: resistive from a start position
    WEAPON         = 0x02  # Simple_Weapon: click/snap from start to end zone
    VIBRATION      = 0x06  # Simple_Vibration: vibrate at frequency+amplitude
    FEEDBACK_FULL  = 0x21  # Official bit-packed Feedback (10-zone activation)
    WEAPON_FULL    = 0x25  # Official bit-packed Weapon
    VIBRATION_FULL = 0x26  # Official bit-packed Vibration
    # ── Logical dispatch keys (not sent as hardware bytes) ────────────────────
    RIGID          = 0xFD  # Max resistance → FEEDBACK at pos=0, force=255
    SLOPE_FEEDBACK = 0xFE  # Linear slope   → FEEDBACK_FULL with bit-packing
    MULTI_POS      = 0xFF  # Multi-zone     → FEEDBACK_FULL with bit-packing


# ── D-pad / hat-switch ────────────────────────────────────────────────────────

class DPadDirection(IntEnum):
    N       = 0
    NE      = 1
    E       = 2
    SE      = 3
    S       = 4
    SW      = 5
    W       = 6
    NW      = 7
    NEUTRAL = 8


# ── Player indicator LEDs ─────────────────────────────────────────────────────

class PlayerLED(IntFlag):
    """Bitmask for the five player-indicator white LEDs."""
    NONE = 0x00
    LED1 = 0x01   # Player 1 (left-most)
    LED2 = 0x02
    LED3 = 0x04   # Centre
    LED4 = 0x08
    LED5 = 0x10   # Player 5 (right-most)

    # Convenience presets
    @classmethod
    def player(cls, n: int) -> "PlayerLED":
        """Return the standard LED pattern for player n (1–4)."""
        patterns = {
            1: cls.LED1,
            2: cls.LED1 | cls.LED2,
            3: cls.LED1 | cls.LED2 | cls.LED3,
            4: cls.LED1 | cls.LED2 | cls.LED3 | cls.LED4,
        }
        return patterns.get(n, cls.NONE)


# ── Microphone LED ────────────────────────────────────────────────────────────

class MicLED(IntEnum):
    OFF   = 0x00
    ON    = 0x01
    BLINK = 0x02


# ── LED brightness ────────────────────────────────────────────────────────────

class LEDBrightness(IntEnum):
    HIGH   = 0x00
    MEDIUM = 0x01
    LOW    = 0x02


# ── Battery charging status ───────────────────────────────────────────────────

class BatteryStatus(IntEnum):
    DISCHARGING = 0x00
    CHARGING    = 0x01
    FULL        = 0x02
    ERROR       = 0x0F
    UNKNOWN     = 0xFF

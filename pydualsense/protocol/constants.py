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

# valid_flag1  (byte 3 of output report)
FLAG1_MIC_MUTE_LED         = 0x01   # Control microphone-mute LED
FLAG1_POWER_SAVE           = 0x02   # Power-save mode control

# valid_flag2  (byte 41 of output report)
FLAG2_LIGHTBAR             = 0x01   # Update light-bar colour
FLAG2_LED_BRIGHTNESS       = 0x02   # Update LED brightness
FLAG2_PLAYER_LEDS          = 0x04   # Update player-indicator LEDs

# Lightbar setup byte  (byte 44 of output report)
LIGHTBAR_CUSTOM_COLOR = 0x01    # Use custom RGB value
LIGHTBAR_RELEASE      = 0x02    # Release / return to default

# ── Adaptive trigger modes ────────────────────────────────────────────────────

class TriggerMode(IntEnum):
    """Adaptive trigger effect modes.

    Each mode occupies byte 0 of the 9-byte trigger-effect block; the
    remaining 8 bytes carry mode-specific parameters.
    """
    OFF             = 0x00  # No resistance
    FEEDBACK        = 0x01  # Resistive feedback from a start position
    WEAPON          = 0x02  # Click/snap at start, rigid beyond
    VIBRATION       = 0x03  # Vibrating effect at a given frequency
    SLOPE_FEEDBACK  = 0x04  # Linearly increasing resistance
    RIGID           = 0x05  # Maximum constant resistance (always on)
    RIGID_A         = 0x06  # Rigid variant A
    RIGID_B         = 0x07  # Rigid variant B
    RIGID_AB        = 0x08  # Rigid combined variant
    MULTI_POS       = 0x0C  # Resistance at multiple discrete positions


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

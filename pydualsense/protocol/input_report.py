"""
Parse raw DualSense HID input reports into structured Python dataclasses.

Bluetooth input report (report ID 0x31, 78 bytes)
──────────────────────────────────────────────────
Offset  Len  Field
  0      1   Report ID (0x31)
  1      1   Reserved
  2      1   Left stick X
  3      1   Left stick Y
  4      1   Right stick X
  5      1   Right stick Y
  6      1   L2 analog (0–255)
  7      1   R2 analog (0–255)
  8      1   Sequence counter
  9      1   Buttons[0]: △(7) ○(6) ✕(5) □(4) dpad(3:0)
 10      1   Buttons[1]: R3(7) L3(6) Options(5) Create(4) R2(3) L2(2) R1(1) L1(0)
 11      1   Buttons[2]: Mute(2) Touchpad(1) PS(0)
 12      1   Buttons[3] / trigger-effect active
 13      4   Reserved
 17      6   Gyro X,Y,Z  (3 × int16 LE)
 23      6   Accel X,Y,Z (3 × int16 LE)
 29      4   Sensor timestamp (uint32 LE)
 33      1   Reserved
 34      4   Touch finger 0: contact(7=inactive, 6:0=id) | X_lo | X_hi(3:0)+Y_lo(3:0) | Y_hi
 38      4   Touch finger 1: same layout
 42      1   Touch timestamp counter
 43      1   AT status 0 (adaptive trigger effect status)
 44      1   AT status 1
 45      4   Host timestamp (uint32 LE)
 49      1   AT status 2
 50      4   Device timestamp (uint32 LE)
 54      1   Battery: status(7:4) | level(3:0)
 55      1   Status 1: headphone(0) / mic(1) flags
 56     18   Reserved / padding
 74      4   CRC-32 (not verified on input side)

USB input report (report ID 0x01, 64 bytes) offsets start at 1 instead of 2
for sticks/triggers (no leading reserved byte after the report ID).
"""

import struct
from dataclasses import dataclass, field
from typing import Optional

from .constants import DPadDirection, BatteryStatus, BT_INPUT_REPORT_ID, USB_INPUT_REPORT_ID


# ── Component state dataclasses ───────────────────────────────────────────────

@dataclass
class Vec3:
    x: int = 0
    y: int = 0
    z: int = 0

    def __iter__(self):
        return iter((self.x, self.y, self.z))


@dataclass
class StickState:
    """Analog stick values.  Raw range 0–255; centre ≈ 128."""
    x: int = 128
    y: int = 128

    def normalised(self) -> tuple:
        """Return (x, y) in the range −1.0 to +1.0."""
        return ((self.x - 128) / 128.0, (self.y - 128) / 128.0)


@dataclass
class ButtonState:
    cross: bool = False
    circle: bool = False
    square: bool = False
    triangle: bool = False
    l1: bool = False
    r1: bool = False
    l2: bool = False    # digital (threshold)
    r2: bool = False    # digital (threshold)
    l3: bool = False
    r3: bool = False
    create: bool = False
    options: bool = False
    ps: bool = False
    touchpad_click: bool = False
    mute: bool = False


@dataclass
class TouchFinger:
    active: bool = False
    id: int = 0
    x: int = 0    # 0–1919
    y: int = 0    # 0–1079


@dataclass
class TouchpadState:
    finger0: TouchFinger = field(default_factory=TouchFinger)
    finger1: TouchFinger = field(default_factory=TouchFinger)

    @property
    def touching(self) -> bool:
        return self.finger0.active or self.finger1.active

    @property
    def active_fingers(self):
        return [f for f in (self.finger0, self.finger1) if f.active]


@dataclass
class BatteryState:
    level: int = 0          # 0–100 (%)
    status: BatteryStatus = BatteryStatus.UNKNOWN

    @property
    def charging(self) -> bool:
        return self.status == BatteryStatus.CHARGING

    @property
    def full(self) -> bool:
        return self.status == BatteryStatus.FULL


@dataclass
class InputState:
    """Full snapshot of controller state parsed from one HID input report."""
    left_stick: StickState = field(default_factory=StickState)
    right_stick: StickState = field(default_factory=StickState)
    l2: int = 0                                     # analog 0–255
    r2: int = 0                                     # analog 0–255
    buttons: ButtonState = field(default_factory=ButtonState)
    dpad: DPadDirection = DPadDirection.NEUTRAL
    touchpad: TouchpadState = field(default_factory=TouchpadState)
    gyro: Vec3 = field(default_factory=Vec3)        # raw int16
    accel: Vec3 = field(default_factory=Vec3)       # raw int16
    battery: BatteryState = field(default_factory=BatteryState)
    sequence: int = 0
    timestamp: int = 0                              # sensor timestamp (µs)
    headphone_connected: bool = False               # 3.5 mm jack has headphone/headset
    mic_connected: bool = False                     # headset mic present on jack


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_touch_finger(data: bytes, offset: int) -> TouchFinger:
    """Parse a 4-byte touch-point entry from the input report."""
    contact   = data[offset]
    x_lo      = data[offset + 1]
    x_hi_y_lo = data[offset + 2]
    y_hi      = data[offset + 3]

    active    = not bool(contact & 0x80)        # bit7=1 means inactive
    finger_id = contact & 0x7F

    x = x_lo | ((x_hi_y_lo & 0x0F) << 8)       # 12-bit X
    y = ((x_hi_y_lo >> 4) & 0x0F) | (y_hi << 4) # 12-bit Y (ish; max 1079)

    return TouchFinger(active=active, id=finger_id, x=x, y=y)


def _parse_battery(raw: int) -> BatteryState:
    status_raw = (raw >> 4) & 0x0F   # upper nibble = charge/plugged status
    level_raw  =  raw       & 0x0F   # lower nibble = battery level  0–10
    level = min(level_raw * 10, 100)
    try:
        status = BatteryStatus(status_raw)
    except ValueError:
        status = BatteryStatus.UNKNOWN
    return BatteryState(level=level, status=status)


# ── Public parsers ────────────────────────────────────────────────────────────

def parse_bt(data: bytes) -> InputState:
    """Parse a 78-byte Bluetooth input report (ID 0x31) into an InputState."""
    if len(data) < 44:
        raise ValueError(f"BT input report too short: {len(data)} bytes")
    if data[0] != BT_INPUT_REPORT_ID:
        raise ValueError(f"Unexpected BT report ID: 0x{data[0]:02X}")

    # Offset base for BT: sticks start at byte 2 (1 report-ID + 1 reserved)
    o = 2
    return _parse_common(data, stick_offset=o)


def parse_usb(data: bytes) -> InputState:
    """Parse a 64-byte USB input report (ID 0x01) into an InputState."""
    if len(data) < 43:
        raise ValueError(f"USB input report too short: {len(data)} bytes")
    if data[0] != USB_INPUT_REPORT_ID:
        raise ValueError(f"Unexpected USB report ID: 0x{data[0]:02X}")

    # Offset base for USB: sticks start at byte 1 (only 1 report-ID byte)
    o = 1
    return _parse_common(data, stick_offset=o)


def parse_input_report(data: bytes) -> InputState:
    """Auto-detect BT vs USB and parse accordingly."""
    if not data:
        raise ValueError("Empty report")
    if data[0] == BT_INPUT_REPORT_ID and len(data) >= 44:
        return parse_bt(data)
    if data[0] == USB_INPUT_REPORT_ID:
        return parse_usb(data)
    raise ValueError(f"Unknown report ID: 0x{data[0]:02X}")


def _parse_common(data: bytes, stick_offset: int) -> InputState:
    """Shared parsing logic; stick_offset=2 for BT, 1 for USB."""
    o = stick_offset

    state = InputState()

    # Analog sticks
    state.left_stick  = StickState(x=data[o],     y=data[o + 1])
    state.right_stick = StickState(x=data[o + 2], y=data[o + 3])

    # Trigger analog values
    state.l2 = data[o + 4]
    state.r2 = data[o + 5]

    # Sequence counter
    state.sequence = data[o + 6]

    # Buttons
    b0 = data[o + 7]
    b1 = data[o + 8]
    b2 = data[o + 9]

    dpad_val = b0 & 0x0F
    state.dpad = DPadDirection(dpad_val) if dpad_val <= 7 else DPadDirection.NEUTRAL

    state.buttons = ButtonState(
        square         = bool(b0 & 0x10),
        cross          = bool(b0 & 0x20),
        circle         = bool(b0 & 0x40),
        triangle       = bool(b0 & 0x80),
        l1             = bool(b1 & 0x01),
        r1             = bool(b1 & 0x02),
        l2             = bool(b1 & 0x04),
        r2             = bool(b1 & 0x08),
        create         = bool(b1 & 0x10),
        options        = bool(b1 & 0x20),
        l3             = bool(b1 & 0x40),
        r3             = bool(b1 & 0x80),
        ps             = bool(b2 & 0x01),
        touchpad_click = bool(b2 & 0x02),
        mute           = bool(b2 & 0x04),
    )

    # IMU sensors (offsets relative to stick_offset + 15 for BT reserved bytes)
    # BT: buttons[3] at o+10, reserved[4] at o+11..14, gyro at o+15
    gyro_off  = o + 15
    accel_off = o + 21
    ts_off    = o + 27

    if len(data) > ts_off + 3:
        gx, gy, gz = struct.unpack_from("<hhh", data, gyro_off)
        state.gyro = Vec3(x=gx, y=gy, z=gz)

        ax, ay, az = struct.unpack_from("<hhh", data, accel_off)
        state.accel = Vec3(x=ax, y=ay, z=az)

        state.timestamp = struct.unpack_from("<I", data, ts_off)[0]

    # Touchpad (o + 32 for BT, slightly different for USB)
    tp_off = o + 32
    if len(data) > tp_off + 7:
        state.touchpad.finger0 = _parse_touch_finger(data, tp_off)
        state.touchpad.finger1 = _parse_touch_finger(data, tp_off + 4)

    # Battery — absolute byte 54 for BT (o=2), 53 for USB (o=1)
    bat_off = o + 52
    if len(data) > bat_off:
        state.battery = _parse_battery(data[bat_off])

    # Status 1 — absolute byte 55 for BT (o=2), 54 for USB (o=1)
    # bit 0: headphone/headset plugged into 3.5 mm jack
    # bit 1: headset mic present on the jack
    status_off = o + 53
    if len(data) > status_off:
        status1 = data[status_off]
        state.headphone_connected = bool(status1 & 0x01)
        state.mic_connected       = bool(status1 & 0x02)

    return state

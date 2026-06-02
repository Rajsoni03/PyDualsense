# HID Protocol Reference

This document describes the raw Bluetooth HID report formats used by the
PS5 DualSense controller.  It is intended for developers who need to work
at the byte level (e.g. porting to another language or debugging).

The library handles all of this automatically — you do not need this
information for normal usage.

---

## Device identifiers

| Field       | Value    | Notes                       |
|-------------|----------|-----------------------------|
| Vendor ID   | `0x054C` | Sony Interactive Entertainment |
| Product ID  | `0x0CE6` | DualSense (BT and USB)      |
| Product ID  | `0x0DF2` | DualSense Edge (BT and USB) |

The controller presents a single HID interface.  Over Bluetooth the extended
report IDs (`0x31`) carry all data; over USB the shorter `0x01` / `0x02`
reports are used.

---

## Bluetooth Input Report — `0x31` (78 bytes)

Every ~4 ms over BT the controller sends this 78-byte report.

```
Offset  Len  Type    Field
──────  ───  ──────  ──────────────────────────────────────────────────────
  0      1   u8      Report ID = 0x31
  1      1   u8      Reserved (padding)
  2      1   u8      Left stick X         (0–255, centre ≈ 128)
  3      1   u8      Left stick Y         (0–255, centre ≈ 128)
  4      1   u8      Right stick X        (0–255, centre ≈ 128)
  5      1   u8      Right stick Y        (0–255, centre ≈ 128)
  6      1   u8      L2 analog            (0–255)
  7      1   u8      R2 analog            (0–255)
  8      1   u8      Sequence counter     (rolls 0–255)
  9      1   u8      Buttons[0]           (see bit map below)
 10      1   u8      Buttons[1]
 11      1   u8      Buttons[2]
 12      1   u8      Buttons[3]           (trigger-effect feedback)
 13      4   u8[4]   Reserved
 17      2   i16le   Gyro X               (~16.4 LSB / °/s)
 19      2   i16le   Gyro Y
 21      2   i16le   Gyro Z
 23      2   i16le   Accel X              (~8192 LSB / g)
 25      2   i16le   Accel Y
 27      2   i16le   Accel Z
 29      4   u32le   Sensor timestamp     (µs counter)
 33      1   u8      Reserved
 34      4   —       Touch finger 0       (see touch encoding below)
 38      4   —       Touch finger 1
 42      1   u8      Touch sequence counter
 43      1   u8      Battery              (see battery encoding below)
 44      2   u8[2]   Reserved
 46     28   u8[28]  Reserved / padding
 74      4   u32le   CRC-32               (not verified on input side)
```

### Buttons[0] — byte 9

| Bit  | Button        |
|------|---------------|
| 7    | Triangle (△)  |
| 6    | Circle (○)    |
| 5    | Cross (✕)     |
| 4    | Square (□)    |
| 3:0  | D-pad hat (0–8, see table below) |

D-pad encoding:

| Value | Direction | Value | Direction |
|-------|-----------|-------|-----------|
| 0     | North (up)    | 4 | South (down)  |
| 1     | North-East    | 5 | South-West    |
| 2     | East (right)  | 6 | West (left)   |
| 3     | South-East    | 7 | North-West    |
| 8     | Neutral       |   |               |

### Buttons[1] — byte 10

| Bit | Button   | Bit | Button  |
|-----|----------|-----|---------|
| 7   | R3       | 3   | R2 (digital) |
| 6   | L3       | 2   | L2 (digital) |
| 5   | Options  | 1   | R1      |
| 4   | Create   | 0   | L1      |

### Buttons[2] — byte 11

| Bit | Button         |
|-----|----------------|
| 2   | Mute           |
| 1   | Touchpad click |
| 0   | PS (Home)      |

### Touch finger encoding (4 bytes each)

```
Byte 0  [7]    = 1 if finger inactive, 0 if active
        [6:0]  = touch ID (0–127, unique per contact)
Byte 1         = X coordinate low 8 bits
Byte 2  [7:4]  = Y coordinate low 4 bits
        [3:0]  = X coordinate high 4 bits
Byte 3         = Y coordinate high 8 bits

X = Byte1 | (Byte2[3:0] << 8)   range 0–1919
Y = Byte2[7:4] | (Byte3 << 4)   range 0–943
```

### Battery encoding — byte 43

```
Bits [7:4]  = battery level  (0–10, multiply by 10 for percentage)
Bits [3:0]  = charging status
              0x00 = discharging
              0x01 = charging
              0x02 = fully charged
              0x0F = error / unknown
```

---

## Bluetooth Output Report — `0x31` (78 bytes)

Sent from host to controller to update rumble, triggers, LEDs, and audio.

```
Offset  Len  Type    Field
──────  ───  ──────  ──────────────────────────────────────────────────────
  0      1   u8      Report ID = 0x31
  1      1   u8      Tag = 0x10
  2      1   u8      valid_flag0   (see flag table)
  3      1   u8      valid_flag1
  4      1   u8      Motor right   (small, high-freq, 0–255)
  5      1   u8      Motor left    (large, low-freq,  0–255)
  6      4   u8[4]   Reserved
 10      1   u8      Headphone audio enable  (1 = on)
 11      1   u8      Headphone volume        (0–0x7F)
 12      1   u8      Speaker audio enable    (1 = on)
 13      1   u8      Speaker volume          (0–0x7F)
 14      1   u8      Microphone volume       (0–0x7F)
 15      1   u8      Audio enable bits
 16      1   u8      Mic select              (0=internal, 1=headset, 2=both)
 17      1   u8      Audio mute flags
 18      9   u8[9]   Right (R2) trigger effect   (see trigger encoding)
 27      9   u8[9]   Left  (L2) trigger effect
 36      5   u8[5]   Reserved
 41      1   u8      valid_flag2
 42      2   u8[2]   Reserved
 44      1   u8      Lightbar setup  (0x01 = custom RGB, 0x02 = release)
 45      1   u8      LED brightness  (0x00 = high, 0x01 = mid, 0x02 = low)
 46      1   u8      Player LEDs     (bitmask, bits 0–4 = LED 1–5)
 47      1   u8      Lightbar R
 48      1   u8      Lightbar G
 49      1   u8      Lightbar B
 50     24   u8[24]  Reserved / padding
 74      4   u32le   CRC-32
```

### valid_flag0 — byte 2

| Bit | Constant                    | Effect                              |
|-----|-----------------------------|-------------------------------------|
| 0   | FLAG0_COMPATIBLE_VIBRATION  | Enable ERM (classic) rumble motors  |
| 1   | FLAG0_HAPTICS_SELECT        | 0 = ERM, 1 = HD haptics             |
| 2   | FLAG0_TRIGGER_R_EFFECT      | Enable right (R2) trigger effect    |
| 3   | FLAG0_TRIGGER_L_EFFECT      | Enable left  (L2) trigger effect    |
| 4   | FLAG0_HEADPHONE_VOLUME      | Update headphone volume             |
| 5   | FLAG0_SPEAKER_VOLUME        | Update speaker volume               |
| 6   | FLAG0_MIC_VOLUME            | Update microphone volume            |
| 7   | FLAG0_AUDIO_CONTROL         | Enable audio control fields         |

### valid_flag1 — byte 3

| Bit | Effect                        |
|-----|-------------------------------|
| 0   | Control microphone-mute LED   |
| 1   | Power-save mode               |

### valid_flag2 — byte 41

| Bit | Effect                         |
|-----|--------------------------------|
| 0   | Update lightbar colour         |
| 1   | Update LED brightness          |
| 2   | Update player indicator LEDs   |

### Trigger effect encoding (9 bytes per trigger)

```
Byte 0   = Mode (TriggerMode enum value)
Bytes 1–8 = Mode-specific parameters
```

#### Mode table

| Mode ID | Name            | Byte 1    | Byte 2     | Byte 3     | Bytes 4–8 |
|---------|-----------------|-----------|------------|------------|-----------|
| `0x00`  | OFF             | —         | —          | —          | —         |
| `0x01`  | FEEDBACK        | start pos | force      | —          | —         |
| `0x02`  | WEAPON          | start pos | end pos    | force      | —         |
| `0x03`  | VIBRATION       | position  | amplitude  | frequency  | —         |
| `0x04`  | SLOPE_FEEDBACK  | start pos | end pos    | start force| end force |
| `0x05`  | RIGID           | —         | —          | —          | —         |
| `0x06`  | RIGID_A         | —         | —          | —          | —         |
| `0x07`  | RIGID_B         | —         | —          | —          | —         |
| `0x08`  | RIGID_AB        | —         | —          | —          | —         |
| `0x0C`  | MULTI_POS       | pos0      | force0     | pos1       | force1, pos2, force2 |

All position and force values are `u8` (0–255).
Frequency is `u8` (approximate Hz).

---

## CRC-32 (Bluetooth output only)

Every BT output report must end with a valid CRC-32 or the controller
ignores it silently.

**Algorithm:** Standard CRC-32 (polynomial `0x04C11DB7`, initial value
`0xFFFFFFFF`, final XOR `0xFFFFFFFF`) via Python's `binascii.crc32`.

**Coverage:** One seed byte `0xA2` prepended to the first 74 bytes of
the report, i.e.:

```
crc_input = bytes([0xA2]) + report[0:74]
crc_value = binascii.crc32(crc_input) & 0xFFFFFFFF
report[74:78] = struct.pack('<I', crc_value)
```

---

## USB differences

Over USB the controller uses shorter reports:

| Report  | ID     | Direction  | Length | Notes                         |
|---------|--------|------------|--------|-------------------------------|
| Input   | `0x01` | Device→Host| 64 B   | No leading reserved byte      |
| Output  | `0x02` | Host→Device| 48 B   | No CRC required               |

The byte offsets for sticks/buttons in the USB input report are shifted
left by one compared to BT (no reserved byte at offset 1).

---

## IMU scaling

The DualSense uses a **TDK InvenSense ICM-42688-P** 6-axis IMU.

| Sensor        | Full-scale range | Raw scale           | Formula               |
|---------------|-----------------|---------------------|-----------------------|
| Gyroscope     | ±2000 °/s       | ~16.4 LSB / (°/s)  | `raw / 16.4` → °/s   |
| Accelerometer | ±4 g            | ~8192 LSB / g       | `raw / 8192` → g     |

Raw values are signed 16-bit integers (little-endian in the report).

---

## Player LED bitmask

```
Bit 0 (LSB) = LED 1  (left-most)
Bit 1       = LED 2
Bit 2       = LED 3  (centre)
Bit 3       = LED 4
Bit 4       = LED 5  (right-most)
Bits 5–7    = unused
```

Standard player assignments:

| Player | LEDs lit  | Bitmask |
|--------|-----------|---------|
| P1     | 1         | `0x01`  |
| P2     | 1, 2      | `0x03`  |
| P3     | 1, 2, 3   | `0x07`  |
| P4     | 1, 2, 3, 4| `0x0F`  |

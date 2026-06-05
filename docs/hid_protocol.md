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
Y = Byte2[7:4] | (Byte3 << 4)   range 0–1079
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
  1      1   u8      Sequence tag  (seq & 0x0F) << 4  — rolling 0–15
  2      1   u8      Tag = 0x10
  3      1   u8      valid_flag0   (see flag table)
  4      1   u8      valid_flag1
  5      1   u8      Motor right   (small, high-freq, 0–255)
  6      1   u8      Motor left    (large, low-freq,  0–255)
  7      1   u8      Headphone volume        (0–0x7F)
  8      1   u8      Speaker volume          (0–0x7F)
  9      1   u8      Microphone volume       (0–0x7F)
 10      1   u8      Audio control
 11      1   u8      Mute LED control
 12      1   u8      Power-save / mute control
 13     11   u8[11]  Right (R2) trigger effect  (1 mode byte + 10 param bytes)
 24     11   u8[11]  Left  (L2) trigger effect  (1 mode byte + 10 param bytes)
 35      4   u8[4]   Reserved
 39      1   u8      Haptic volume
 40      1   u8      Audio control 2
 41      1   u8      valid_flag2
 42      2   u8[2]   Reserved
 44      1   u8      Lightbar setup  (0x00 = custom RGB, 0x02 = release to default)
 45      1   u8      LED brightness  (0x00 = high, 0x01 = mid, 0x02 = low)
 46      1   u8      Player LEDs     (bitmask, bits 0–4 = LED 1–5)
 47      1   u8      Lightbar R
 48      1   u8      Lightbar G
 49      1   u8      Lightbar B
 50     24   u8[24]  Reserved / padding
 74      4   u32le   CRC-32
```

### valid_flag0 — byte 3

| Bit | Constant                    | Value  | Effect                                                   |
|-----|-----------------------------|--------|----------------------------------------------------------|
| 0   | FLAG0_COMPATIBLE_VIBRATION  | `0x01` | Enable ERM rumble motors                                 |
| 1   | FLAG0_HAPTICS_SELECT        | `0x02` | 0 = ERM, 1 = HD haptics; **both bits 0+1 must be set for ERM rumble** |
| 2   | FLAG0_TRIGGER_R_EFFECT      | `0x04` | Enable right (R2) trigger effect                         |
| 3   | FLAG0_TRIGGER_L_EFFECT      | `0x08` | Enable left  (L2) trigger effect                         |
| 4   | FLAG0_HEADPHONE_VOLUME      | `0x10` | Update headphone volume                                  |
| 5   | FLAG0_SPEAKER_VOLUME        | `0x20` | Update speaker volume                                    |
| 6   | FLAG0_MIC_VOLUME            | `0x40` | Update microphone volume                                 |
| 7   | FLAG0_AUDIO_CONTROL         | `0x80` | Enable audio control fields                              |

> **Important:** ERM rumble requires **both** `FLAG0_COMPATIBLE_VIBRATION (0x01)` and
> `FLAG0_HAPTICS_SELECT (0x02)` to be set.  Setting only bit 0 produces no physical vibration.

### valid_flag1 — byte 4

| Bit | Constant                | Value  | Effect                                            |
|-----|-------------------------|--------|---------------------------------------------------|
| 0   | FLAG1_MIC_MUTE_LED      | `0x01` | Control microphone-mute LED                       |
| 1   | FLAG1_POWER_SAVE        | `0x02` | Power-save mode                                   |
| 2   | FLAG1_LIGHTBAR_COLOR    | `0x04` | Apply custom lightbar RGB from bytes 47–49        |
| 3   | FLAG1_LIGHTBAR_DEFAULT  | `0x08` | Release lightbar to controller default colour     |
| 4   | FLAG1_PLAYER_LEDS       | `0x10` | Update player indicator LEDs from byte 46         |

To set a custom lightbar colour: set bit 2 (`FLAG1_LIGHTBAR_COLOR`) and clear bit 3
(`FLAG1_LIGHTBAR_DEFAULT`).

### valid_flag2 — byte 41

| Bit | Constant              | Value  | Effect                  |
|-----|-----------------------|--------|-------------------------|
| 0   | FLAG2_LED_BRIGHTNESS  | `0x01` | Update LED brightness   |

### Trigger effect encoding (11 bytes per trigger)

Each trigger block is **11 bytes**: 1 mode byte followed by 10 parameter bytes.

```
Byte 0     = Mode ID (TriggerMode enum value)
Bytes 1–10 = Mode-specific parameters (unused bytes = 0x00)
```

#### Simple modes (used by the high-level API)

| Mode ID | Name       | param[0]  | param[1]   | param[2]   | Notes                         |
|---------|------------|-----------|------------|------------|-------------------------------|
| `0x01`  | FEEDBACK   | start pos | force      | —          | Resistive from start position |
| `0x02`  | WEAPON     | start pos | end pos    | force      | Click at start, rigid to end  |
| `0x05`  | OFF        | —         | —          | —          | No effect; returns to neutral |
| `0x06`  | VIBRATION  | frequency | amplitude  | position   | Vibrate at set frequency      |

All position, force, amplitude, and frequency values are `u8` (0–255).

#### Official bit-packed modes (multi-zone effects)

| Mode ID | Name           | Description                                   |
|---------|----------------|-----------------------------------------------|
| `0x21`  | FEEDBACK_FULL  | 10-zone bit-packed feedback (active_zones + force_zones) |
| `0x25`  | WEAPON_FULL    | Official bit-packed weapon                    |
| `0x26`  | VIBRATION_FULL | Official bit-packed vibration                 |

`FEEDBACK_FULL` bit-packing (used internally for `slope` and `multi_pos` effects):
```
param[0–1]  = active_zones  (10-bit mask; bit i = zone i active)
param[2–5]  = force_zones   (30-bit value; 3 bits per zone, value = strength − 1)
```

---

### Audio routing — `audio_control` byte (offset 10)

| Value  | Routing           |
|--------|-------------------|
| `0x30` | Built-in speaker  |
| `0x00` | 3.5 mm headphone  |

Set by `set_speaker_volume()` and `set_headphone_volume()` respectively.
`FLAG0_AUDIO_CONTROL (0x80)` and the corresponding volume flag must also be set.
ERM rumble flags (`FLAG0_COMPATIBLE_VIBRATION`, `FLAG0_HAPTICS_SELECT`) must be
**clear** when sending audio bytes; the firmware ignores audio if rumble flags
are set in the same report.

---

## Bluetooth Audio Report — `0x36` (398 bytes)

Used to stream Opus-encoded audio to the DualSense built-in speaker over
Bluetooth.  Sent via `hid.Device.write()` on the interrupt channel at
approximately 100 packets/second (one 10 ms Opus frame per packet).

```
Offset  Len   Field
──────  ────  ──────────────────────────────────────────────────
  0      1    Report ID = 0x36
  1      1    Sequence tag: (seq & 0x0F) << 4  (rolling 0–15)
  2      1    Tag = 0x00
  3      1    Tag = 0x00
  4     63    Controller state (see Output Report 0x31, bytes 3–65)
 67      2    Reserved = 0x00 0x00
 69      1    Audio data marker = 0xFF
 70      2    Audio frame length (little-endian u16)
 72      2    Audio frame tag
 74      8    Reserved = 0x00 …
 82      2    Audio sequence counter (rolling 0–255)
 84      2    Reserved = 0x00 0x00
 86     200   Opus-encoded audio frame (CBR, padded to 200 bytes)
286    108    Reserved / padding
394      4    CRC-32 (see below)
```

### State bytes (offsets 4–66)

The 63-byte state block embedded in the 0x36 report uses **Bluetooth-specific
values** verified by the DS5Dongle project.  Key fields:

| State offset | Value  | Meaning                                              |
|--------------|--------|------------------------------------------------------|
| 0            | `0xFD` | flag0 — all enable bits set                          |
| 1            | `0xF7` | flag1                                                |
| 4            | `0x7F` | headphone_vol                                        |
| 5            | `0x64` | speaker_vol (default; override with actual volume)   |
| 6            | `0xFF` | mic_vol                                              |
| 7            | `0x09` | audio_ctrl — BT-specific value (NOT `0x30`)          |
| 9            | `0x0F` | power_save_mute_ctrl                                 |
| 37           | `0x0A` | audio_ctrl_2                                         |
| 38           | `0x07` | valid_flag2                                          |
| 41           | `0x02` | lightbar_setup                                       |
| 42           | `0x01` | led_brightness                                       |
| 44–46        | R/G/B  | lightbar colour                                      |

Using the standard USB state values (e.g. `audio_ctrl = 0x30`) causes the
controller to ignore the audio data silently.

### Opus encoding parameters

| Parameter       | Value                             |
|-----------------|-----------------------------------|
| Sample rate     | 48 000 Hz                         |
| Channels        | 2 (stereo)                        |
| Application     | OPUS_APPLICATION_AUDIO            |
| Bitrate         | 160 000 bps (CBR)                 |
| VBR             | Off (`OPUS_SET_VBR = 0`)          |
| Frame size      | 480 samples = 10 ms               |
| Max frame bytes | 200 (padded to exactly 200 bytes) |

### CRC-32 for report 0x36

Same algorithm as the standard output report CRC but with a different seed:

```
crc_input = bytes([0xA2]) + pkt[0:394]
crc_value = binascii.crc32(crc_input) & 0xFFFFFFFF
pkt[394:398] = struct.pack('<I', crc_value)
```

---

## USB Feature Report — `0x80` (waveout control)

Enables the audio signal path on USB-connected controllers via the firmware
test interface.  Sent with `hid.Device.send_feature_report()`.

Report layout: `[report_id=0x80, device_id, action_id, param0, param1, ...]`
padded to 64 bytes total (63 data bytes + 1 report-ID byte prepended by hidapi).

### Enable speaker (`controlWaveOut(device, true, 'speaker')`)

**Step 1** — configure routing:
```
device_id = 0x06  (AUDIO)
action_id = 0x04  (BUILTIN_MIC_CALIB_DATA_VERIFY)
params[2]  = 0x08
```

**Step 2** — enable waveout (after 20 ms):
```
device_id  = 0x06
action_id  = 0x02  (WAVEOUT_CTRL)
params     = [1, 1, 0]
```

### Enable headphone (`controlWaveOut(device, true, 'headphone')`)

**Step 1** — configure routing:
```
device_id  = 0x06
action_id  = 0x04
params[4]  = 0x04
params[6]  = 0x06
```

**Step 2** — enable waveout (after 20 ms): same as speaker step 2.

### Disable (`controlWaveOut(device, false)`)

```
device_id  = 0x06
action_id  = 0x02
params     = [0, 1, 0]
```

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

Standard PlayStation symmetric patterns (`PlayerLED.player(n)`):

| Player | Pattern | LEDs active          | Bitmask |
|--------|---------|----------------------|---------|
| P1     | `··●··` | LED3 (centre)        | `0x04`  |
| P2     | `·●·●·` | LED2, LED4           | `0x0A`  |
| P3     | `●·●·●` | LED1, LED3, LED5     | `0x15`  |
| P4     | `●●·●●` | LED1, LED2, LED4, LED5 | `0x1B` |
| All    | `●●●●●` | All five LEDs        | `0x1F`  |

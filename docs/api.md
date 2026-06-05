# API Reference

## `pydualsense.DualSense`

The main entry point for controlling the PS5 DualSense controller.

```python
from pydualsense import DualSense
```

### Constructor

```python
DualSense()
```

Creates an unconnected controller instance.  Call `connect()` before
any other method.

---

### Connection

#### `connect(serial=None)`

Connect to a DualSense controller.

| Parameter | Type   | Default | Description                                    |
|-----------|--------|---------|------------------------------------------------|
| `serial`  | `str`  | `None`  | Serial number to target a specific device.     |
|           |        |         | `None` connects to the first device found.     |

Raises `RuntimeError` if no controller is found.  Sets the light bar to
dim blue and player-1 LED pattern on success.

```python
ds.connect()                        # first available
ds.connect(serial="ABCD1234")       # specific device
```

#### `disconnect()`

Stop the event loop (if running) and close the HID device.

#### Context manager

```python
with DualSense() as ds:
    # auto-connect on entry, auto-disconnect on exit
    pass
```

---

### Reading input

#### `read() → InputState`

Block until one HID input report arrives and return the parsed state.
Raises `TimeoutError` if no report arrives within 1 second.

```python
state = ds.read()
```

#### `state` *(property)*

Returns the most recent `InputState` without blocking.  `None` until
the first `read()` or callback invocation.

```python
current = ds.state
```

---

### Event loop

#### `listen(callback, poll_interval=0.001)`

Start a **blocking** read loop.  Calls `callback(state)` on every new
input report.  Returns when Ctrl-C is pressed.

| Parameter       | Type       | Description                                |
|-----------------|------------|--------------------------------------------|
| `callback`      | `callable` | `fn(InputState) → None`                   |
| `poll_interval` | `float`    | Sleep time (s) between empty reads         |

```python
ds.listen(lambda s: print(s.buttons.cross))
```

#### `listen_async(callback)`

Start the event loop in a **background daemon thread**.  Returns immediately.

```python
ds.listen_async(my_handler)
# main thread continues
```

#### `stop()`

Signal the event loop to stop and wait for the background thread to exit.

---

### Rumble / haptics

#### `set_rumble(right=0, left=0)`

Set ERM rumble motor intensities.

| Parameter | Type  | Range  | Motor                        |
|-----------|-------|--------|------------------------------|
| `right`   | `int` | 0–255  | Right (small, high-frequency)|
| `left`    | `int` | 0–255  | Left  (large, low-frequency) |

```python
ds.set_rumble(right=200, left=100)
ds.set_rumble(0, 0)    # off
```

> **Note:** The DualSense requires both `FLAG0_COMPATIBLE_VIBRATION` (bit 0) and
> `FLAG0_HAPTICS_SELECT` (bit 1) to be set in `valid_flag0` to activate ERM motors.
> The library sets both automatically — you do not need to handle this manually.

#### `stop_rumble()`

Stop both rumble motors.

---

### Adaptive triggers

#### `set_trigger_effect(side, effect)`

Apply an adaptive trigger effect.

| Parameter | Type            | Description                                  |
|-----------|-----------------|----------------------------------------------|
| `side`    | `str`           | `"left"`, `"l"`, `"l2"`, `"right"`, `"r"`, `"r2"` |
| `effect`  | `TriggerEffect` | Effect from `TriggerEffect.*` factories      |

```python
from pydualsense.features.triggers import TriggerEffect

ds.set_trigger_effect("right", TriggerEffect.weapon())
ds.set_trigger_effect("left",  TriggerEffect.feedback(start=60, force=160))
```

#### `set_trigger_off(side="both")`

Disable adaptive effects on one or both triggers.

```python
ds.set_trigger_off()           # both
ds.set_trigger_off("right")
```

---

### LEDs

#### `set_led(r, g, b)`

Set the light-bar RGB colour.  Values are clamped to 0–255.

```python
ds.set_led(0, 0, 255)     # blue
ds.set_led(0, 0, 0)       # off
```

#### `set_player_leds(mask)`

Set the player-indicator LEDs via a bitmask.

```python
from pydualsense import PlayerLED

ds.set_player_leds(PlayerLED.LED1)           # one dot
ds.set_player_leds(PlayerLED.player(2))      # two dots (player 2)
ds.set_player_leds(PlayerLED.NONE)           # all off
```

#### `set_mic_led(mode)`

Set the microphone-mute indicator LED.

```python
from pydualsense import MicLED

ds.set_mic_led(MicLED.ON)
ds.set_mic_led(MicLED.BLINK)
ds.set_mic_led(MicLED.OFF)
```

---

### Audio — volume control

#### `set_speaker_volume(volume)`

Set built-in speaker volume (0–255) and route audio output to the speaker.
Also sets `audio_control = 0x30` and clears ERM rumble flags so the firmware
processes the audio bytes.

#### `set_headphone_volume(volume)`

Set headphone jack volume (0–255) and route audio to the 3.5 mm output.
Sets `audio_control = 0x00`.

#### `set_mic_volume(volume)`

Set microphone input gain (0–255).

---

### Audio — USB waveout (feature report 0x80)

These methods use the firmware test interface (`report 0x80`) to enable the
audio signal path on a USB-connected controller.  Call after setting the
desired volume and before routing OS audio to the DualSense audio device.

#### `enable_speaker_audio()`

Enable the built-in speaker via the waveout interface.  Mirrors
`controlWaveOut(device, true, 'speaker')` from the reference implementation.

```python
ds.set_speaker_volume(200)
ds.enable_speaker_audio()
# Now play audio through the OS DualSense audio device
```

#### `enable_headphone_audio()`

Enable the headphone jack via the waveout interface.

```python
ds.set_headphone_volume(180)
ds.enable_headphone_audio()
```

#### `disable_audio()`

Disable the audio waveout path.

```python
ds.disable_audio()
```

---

### Audio — Bluetooth speaker streaming

Streams Opus-encoded audio to the DualSense built-in speaker over Bluetooth
using HID report `0x36`.

**Requirements:**
- `pip install cffi`
- libopus native library (`brew install opus` on macOS, `apt install libopus-dev` on Linux)

#### `stream_bt_speaker(source="tone", freq=440.0, amplitude=0.6, duration=None, in_device=None) → BTAudioStream`

Start streaming audio to the controller speaker.

| Parameter   | Type    | Default | Description                                              |
|-------------|---------|---------|----------------------------------------------------------|
| `source`    | `str`   | `"tone"`| `"tone"` — sine wave, or `"mic"` — host mic passthrough |
| `freq`      | `float` | `440.0` | Tone frequency in Hz (source="tone" only)               |
| `amplitude` | `float` | `0.6`   | Tone amplitude 0–1 (source="tone" only)                 |
| `duration`  | `float` | `None`  | Auto-stop after this many seconds; `None` = until `stop_bt_speaker()` |
| `in_device` | `int`   | `None`  | Input device index for source="mic"                     |

Returns the `BTAudioStream` instance (already started).

```python
# Play a 440 Hz tone for 3 seconds
stream = ds.stream_bt_speaker(source="tone", freq=440.0, duration=3.0)

# Stream host microphone input to the controller speaker
stream = ds.stream_bt_speaker(source="mic")
ds.stop_bt_speaker()
```

> **Bluetooth mic note:** The DualSense microphone is only accessible over USB
> (USB Audio Class interface).  There is no HID path to capture mic audio
> over Bluetooth.

#### `stop_bt_speaker()`

Stop BT speaker streaming if running.

#### `write_bt_audio_frame(opus_bytes, state_bytes)`

Low-level: send one pre-encoded 10 ms Opus frame directly.

| Parameter    | Type    | Description                                           |
|--------------|---------|-------------------------------------------------------|
| `opus_bytes` | `bytes` | 200-byte CBR Opus packet (padded to 200 if shorter)   |
| `state_bytes`| `bytes` | 63-byte state from `make_bt_state_bytes()`            |

---

## `BTAudioStream`

```python
from pydualsense.features.bt_audio import BTAudioStream
```

Manages the background thread that encodes and sends audio frames to the
controller.  Normally obtained via `DualSense.stream_bt_speaker()`.

### Constructor

```python
BTAudioStream(send_fn, speaker_vol=100, rgb=(0, 0, 64))
```

| Parameter    | Type       | Description                                    |
|--------------|------------|------------------------------------------------|
| `send_fn`    | `callable` | `fn(opus_bytes, state_bytes)` — called per frame |
| `speaker_vol`| `int`      | Speaker volume embedded in state bytes (0–255) |
| `rgb`        | `tuple`    | Light-bar colour embedded in state bytes       |

### Methods

#### `start(source="tone", freq=440.0, amplitude=0.6, in_device=None)`

Start the streaming thread.

#### `stop()`

Stop the streaming thread and wait for it to exit.

---

## `InputState`

Snapshot of all controller inputs parsed from one HID report.

```python
from pydualsense.protocol.input_report import InputState
```

### Analog sticks

```python
state.left_stick.x            # raw 0–255 (centre ≈ 128)
state.left_stick.y
state.left_stick.normalised() # → (float, float) each -1.0 … +1.0

state.right_stick.x
state.right_stick.y
state.right_stick.normalised()
```

### Triggers

```python
state.l2    # analog 0–255
state.r2    # analog 0–255

state.buttons.l2   # digital (bool)
state.buttons.r2   # digital (bool)
```

### Buttons

All fields are `bool`.

| Field             | Button              |
|-------------------|---------------------|
| `cross`           | ✕ (X)               |
| `circle`          | ○                   |
| `square`          | □                   |
| `triangle`        | △                   |
| `l1` / `r1`       | Shoulder bumpers    |
| `l2` / `r2`       | Trigger digital     |
| `l3` / `r3`       | Stick clicks        |
| `create`          | Create / Share      |
| `options`         | Options             |
| `ps`              | PS / Home           |
| `mute`            | Mic mute            |
| `touchpad_click`  | Touchpad physical press |

```python
if state.buttons.triangle:
    ds.set_led(255, 255, 0)
```

### D-pad

```python
from pydualsense import DPadDirection

state.dpad              # DPadDirection enum
state.dpad.name         # 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'NEUTRAL'

if state.dpad == DPadDirection.N:
    print("Up!")
```

### Touchpad

```python
state.touchpad.touching           # bool: any finger active
state.touchpad.active_fingers     # list of active TouchFinger objects

f = state.touchpad.finger0
f.active                          # bool
f.id                              # int (tracking ID)
f.x                               # 0–1919
f.y                               # 0–1079

state.buttons.touchpad_click      # physical press
```

### Motion sensors

```python
# Raw int16 values (ICM-42688-P)
state.gyro.x, state.gyro.y, state.gyro.z       # ~16.4 LSB / °/s
state.accel.x, state.accel.y, state.accel.z    # ~8192 LSB / g

# Convert to physical units:
from pydualsense.features.motion import MotionState
ms = MotionState(state.gyro, state.accel)
gx, gy, gz = ms.gyro_dps()    # degrees / second
ax, ay, az = ms.accel_g()     # g-force
```

### Battery

```python
state.battery.level      # 0–100 (%)
state.battery.charging   # bool
state.battery.full       # bool
state.battery.status     # BatteryStatus enum
```

### Audio jack / mic status

```python
state.headphone_connected   # bool — 3.5 mm jack inserted
state.mic_connected         # bool — microphone detected (USB only)
```

Useful for switching between speaker and headphone output:

```python
state = ds.read()
if state.headphone_connected:
    ds.set_headphone_volume(180)
    ds.enable_headphone_audio()
else:
    ds.set_speaker_volume(200)
    ds.enable_speaker_audio()
```

---

## `TriggerEffect`

Factory class for adaptive trigger effects.

```python
from pydualsense.features.triggers import TriggerEffect
```

| Factory method                                        | Mode             |
|-------------------------------------------------------|------------------|
| `TriggerEffect.off()`                                 | OFF              |
| `TriggerEffect.feedback(start, force)`                | FEEDBACK         |
| `TriggerEffect.weapon(start, end, force)`             | WEAPON           |
| `TriggerEffect.vibration(position, amplitude, frequency)` | VIBRATION    |
| `TriggerEffect.slope(start, end, start_force, end_force)` | SLOPE_FEEDBACK |
| `TriggerEffect.rigid()`                               | RIGID            |
| `TriggerEffect.multi_pos(positions, forces)`          | MULTI_POS        |

### Parameter reference

**`feedback(start=0, force=128)`**
- `start` (0–255): trigger position where resistance begins
- `force` (0–255): resistance strength

**`weapon(start=50, end=100, force=200)`**
- `start` (0–255): position where click occurs
- `end` (0–255): position where trigger locks rigid
- `force` (0–255): click and resistance strength

**`vibration(position=0, amplitude=128, frequency=25)`**
- `position` (0–255): trigger position where effect activates
- `amplitude` (0–255): vibration intensity
- `frequency` (0–255): vibration frequency in Hz

**`slope(start=0, end=255, start_force=0, end_force=255)`**
- Linear ramp from `start_force` at `start` to `end_force` at `end`

**`multi_pos(positions, forces)`**
- `positions`: list of up to 3 trigger positions (0–255 each)
- `forces`: corresponding resistance forces (0–255 each)

---

## `PlayerLED`

`IntFlag` enum for player-indicator LEDs.

```python
from pydualsense import PlayerLED

PlayerLED.LED1          # 0x01  (left-most)
PlayerLED.LED2          # 0x02
PlayerLED.LED3          # 0x04  (centre)
PlayerLED.LED4          # 0x08
PlayerLED.LED5          # 0x10  (right-most)
PlayerLED.ALL           # 0x1F  (all five)
PlayerLED.NONE          # 0x00

# Standard PlayStation symmetric patterns:
PlayerLED.player(1)     # 0x04  ··●··  centre dot only
PlayerLED.player(2)     # 0x0A  ·●·●·  two inner-symmetrical
PlayerLED.player(3)     # 0x15  ●·●·●  alternating 1+3+5
PlayerLED.player(4)     # 0x1B  ●●·●●  all except centre

# Combine arbitrary LEDs:
mask = PlayerLED.LED2 | PlayerLED.LED4
ds.set_player_leds(mask)
```

---

## `MicLED`

```python
from pydualsense import MicLED
MicLED.OFF    # 0
MicLED.ON     # 1
MicLED.BLINK  # 2
```

---

## `DPadDirection`

```python
from pydualsense import DPadDirection
DPadDirection.N       # 0  (up)
DPadDirection.NE      # 1
DPadDirection.E       # 2  (right)
DPadDirection.SE      # 3
DPadDirection.S       # 4  (down)
DPadDirection.SW      # 5
DPadDirection.W       # 6  (left)
DPadDirection.NW      # 7
DPadDirection.NEUTRAL # 8
```

---

## Utility functions

### `pydualsense.utils.deadzone`

```python
from pydualsense.utils.deadzone import (
    apply_deadzone,            # single axis
    apply_deadzone_circular,   # 2D radial deadzone
    apply_deadzone_square,     # 2D per-axis independent
)

# Single axis
y = apply_deadzone(raw_value, threshold=0.10)

# Circular (recommended for sticks)
nx, ny = apply_deadzone_circular(raw_x, raw_y, threshold=0.10)
```

All functions operate on normalised float values in the range −1.0 to +1.0.
Values inside the deadzone snap to 0; the rest is rescaled to maintain the
full output range.

### `pydualsense.utils.color`

```python
from pydualsense.utils.color import named_color, rgb_from_hsv

r, g, b = named_color("orange")           # (255, 128, 0)
r, g, b = rgb_from_hsv(0.0, 1.0, 1.0)    # red
```

Named colours: `red`, `green`, `blue`, `white`, `off`, `yellow`, `cyan`,
`magenta`, `orange`, `purple`, `pink`, `player1`–`player4`.

### `pydualsense.utils.filters`

```python
from pydualsense.utils.filters import LowPassFilter, LowPassFilter3D

f = LowPassFilter(alpha=0.1)          # alpha=1.0 = no filtering
smoothed = f.update(raw_gyro_x)

f3d = LowPassFilter3D(alpha=0.1)
gx, gy, gz = f3d.update(raw_x, raw_y, raw_z)
```

### `pydualsense.features.motion.MotionState`

```python
from pydualsense.features.motion import MotionState

ms = MotionState(gyro=state.gyro, accel=state.accel)
gx, gy, gz = ms.gyro_dps()     # °/s
ax, ay, az = ms.accel_g()      # g
```

### `pydualsense.transport.discovery`

```python
from pydualsense.transport.discovery import list_controllers, find_controller

controllers = list_controllers()    # list of ControllerInfo
info = find_controller()            # first found
info = find_controller(serial="X")  # by serial
```

`ControllerInfo` fields: `path`, `vendor_id`, `product_id`, `serial_number`,
`manufacturer`, `product`, `interface`.

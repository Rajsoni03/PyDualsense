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

### Audio

#### `set_speaker_volume(volume)`

Set built-in speaker volume (0–127).

#### `set_headphone_volume(volume)`

Set headphone output volume (0–127).

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
f.y                               # 0–943

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

PlayerLED.LED1          # 0x01
PlayerLED.LED2          # 0x02
PlayerLED.LED3          # 0x04
PlayerLED.LED4          # 0x08
PlayerLED.LED5          # 0x10
PlayerLED.NONE          # 0x00

PlayerLED.player(1)     # LED1
PlayerLED.player(2)     # LED1 | LED2
PlayerLED.player(3)     # LED1 | LED2 | LED3
PlayerLED.player(4)     # LED1 | LED2 | LED3 | LED4

# Combine:
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

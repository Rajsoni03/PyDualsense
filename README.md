# PyDualsense

A Python library for full access to the PS5 DualSense controller over **Bluetooth** and USB.

Exposes every hardware feature — adaptive triggers, haptic rumble, RGB light bar,
touchpad, gyroscope/accelerometer, speaker, and microphone — through a clean,
OS-agnostic API built on `hidapi`.

---

## Features

| Category           | Features                                                              |
|--------------------|-----------------------------------------------------------------------|
| **Input**          | Analog sticks (L/R), triggers (L2/R2 analog + digital)               |
|                    | 15 buttons (face, shoulder, L3/R3, PS, mute, touchpad click)         |
|                    | D-pad (8 directions + neutral)                                        |
|                    | Dual-finger capacitive touchpad (1920 × 1080, per-finger tracking)    |
|                    | Gyroscope X/Y/Z + Accelerometer X/Y/Z (ICM-42688-P IMU)             |
|                    | Battery level (%) + charging status                                   |
|                    | Headphone / jack connected status                                     |
| **Output**         | ERM rumble motors (left = large/LF, right = small/HF, 0–255 each)   |
|                    | Adaptive triggers — 10 modes with full parameter control              |
|                    | RGB light bar (0–255 per channel)                                    |
|                    | 5 player-indicator LEDs (bitmask)                                     |
|                    | Microphone-mute LED (off / on / blink)                               |
|                    | Speaker + microphone + headphone volume (0–255 each)                 |
|                    | **Bluetooth speaker streaming** — Opus-encoded audio via HID report 0x36 |
|                    | **USB speaker/headphone** — waveout enable via feature report 0x80   |

### Adaptive Trigger Modes

| Factory                  | Description                                              |
|--------------------------|----------------------------------------------------------|
| `TriggerEffect.off()`    | No resistance; trigger at neutral                        |
| `TriggerEffect.feedback()` | Resistive feedback starting at a set position          |
| `TriggerEffect.weapon()` | Click/snap at start position, rigid beyond               |
| `TriggerEffect.vibration()` | Vibrating effect at configurable frequency            |
| `TriggerEffect.slope()`  | Linearly increasing resistance from start to end         |
| `TriggerEffect.rigid()`  | Maximum constant resistance from trigger start           |
| `TriggerEffect.multi_pos()` | Resistance at up to 10 discrete positions             |

---

## Installation

```bash
pip install hid
pip install pydualsense        # once published
# or install from source:
git clone https://github.com/your-org/PyDualsenseBT
cd PyDualsenseBT
pip install -e .
```

### Linux udev rule (required for Bluetooth HID access)

```bash
echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", MODE="0666"' \
    | sudo tee /etc/udev/rules.d/70-dualsense.rules
sudo udevadm trigger
```

### Pair the controller (Linux)

```bash
bluetoothctl
> power on
> agent on
> scan on
# hold PS + Create on the controller until LED blinks rapidly
> pair <MAC>
> connect <MAC>
> trust <MAC>
```

See [docs/installation.md](docs/installation.md) for Windows and macOS setup.

---

## Quick Start

```python
from pydualsense import DualSense
from pydualsense.features.triggers import TriggerEffect

with DualSense() as ds:
    # Read one snapshot
    state = ds.read()
    print(f"Left stick: {state.left_stick.normalised()}")
    print(f"Battery:    {state.battery.level}%")

    # Output
    ds.set_led(0, 0, 255)                                   # blue light bar
    ds.set_rumble(right=128, left=64)                       # rumble
    ds.set_trigger_effect("right", TriggerEffect.weapon())  # adaptive trigger
```

### Continuous event loop

```python
def on_state(state):
    if state.buttons.cross:
        print("Cross pressed!")

ds = DualSense()
ds.connect()
ds.listen(on_state)       # blocking; Ctrl-C to stop
```

### Background thread

```python
ds.listen_async(on_state)
# ... do other work ...
ds.stop()
ds.disconnect()
```

---

## API Overview

### `DualSense`

| Method / Property                          | Description                                      |
|--------------------------------------------|--------------------------------------------------|
| `connect(serial=None)`                     | Connect to first (or specific) controller        |
| `disconnect()`                             | Stop loop and close device                       |
| `read() → InputState`                      | Block for one input report                       |
| `listen(callback)`                         | Blocking event loop                              |
| `listen_async(callback)`                   | Background-thread event loop                     |
| `stop()`                                   | Stop background loop                             |
| `state`                                    | Most recent InputState (property)                |
| `set_rumble(right, left)`                  | ERM rumble 0–255                                 |
| `stop_rumble()`                            | Silence both motors                              |
| `set_trigger_effect(side, TriggerEffect)`  | Adaptive trigger effect                          |
| `set_trigger_off(side="both")`             | Disable trigger effects                          |
| `set_led(r, g, b)`                         | Light-bar colour 0–255                           |
| `set_player_leds(mask)`                    | Player indicator LEDs (PlayerLED bitmask)        |
| `set_mic_led(MicLED)`                      | Microphone-mute LED                              |
| `set_speaker_volume(vol)`                  | Built-in speaker 0–255                           |
| `set_headphone_volume(vol)`                | Headphone output 0–255                           |
| `set_mic_volume(vol)`                      | Microphone gain 0–255                            |
| `enable_speaker_audio()`                   | Enable USB speaker via feature report 0x80       |
| `enable_headphone_audio()`                 | Enable USB headphone via feature report 0x80     |
| `disable_audio()`                          | Disable USB audio waveout                        |
| `stream_bt_speaker(source, …)`             | Stream Opus audio to BT speaker (returns BTAudioStream) |
| `stop_bt_speaker()`                        | Stop BT audio stream                             |

### `InputState`

```
state.left_stick.x / .y          # raw 0–255
state.left_stick.normalised()    # (x, y) as -1.0 … +1.0
state.right_stick                # same
state.l2 / state.r2              # trigger analog 0–255
state.buttons.cross              # True/False (all 15 buttons)
state.dpad                       # DPadDirection enum
state.touchpad.finger0 / .finger1  # TouchFinger(active, id, x, y)
state.gyro.x / .y / .z           # raw int16
state.accel.x / .y / .z          # raw int16
state.battery.level              # 0–100 %
state.battery.charging           # bool
state.headphone_connected        # bool
state.mic_connected              # bool
```

### `TriggerEffect` factories

```python
TriggerEffect.off()
TriggerEffect.feedback(start=60, force=160)
TriggerEffect.weapon(start=40, end=100, force=220)
TriggerEffect.vibration(position=0, amplitude=200, frequency=30)
TriggerEffect.slope(start=0, end=255, start_force=0, end_force=255)
TriggerEffect.rigid()
TriggerEffect.multi_pos(positions=[50, 120, 200], forces=[180, 180, 180])
```

### Helpers

```python
from pydualsense import PlayerLED, MicLED
from pydualsense.utils.color import named_color, rgb_from_hsv
from pydualsense.utils.deadzone import apply_deadzone_circular

ds.set_player_leds(PlayerLED.player(1))          # standard P1 pattern
ds.set_mic_led(MicLED.BLINK)
r, g, b = named_color("orange")
r, g, b = rgb_from_hsv(0.6, 1.0, 1.0)
nx, ny  = apply_deadzone_circular(nx, ny, 0.10)
```

---

## Examples

| Script                           | Demonstrates                                                   |
|----------------------------------|----------------------------------------------------------------|
| `examples/basic_input.py`        | All inputs printed to terminal                                 |
| `examples/rumble_demo.py`        | Rumble motor patterns (left LF / right HF)                    |
| `examples/adaptive_triggers.py`  | Every trigger mode with timed holds                           |
| `examples/led_colors.py`         | Rainbow sweep, named presets, player LEDs, mic LED            |
| `examples/touchpad_viz.py`       | ASCII visualisation of dual-finger positions                   |
| `examples/motion_orientation.py` | Live gyro/accel readout in °/s and g                          |
| `examples/robotics_gamepad.py`   | Interactive terminal UI — 4 drive modes, adaptive triggers, touchpad, IMU |
| `examples/asteroid_miner.py`     | Full terminal arcade game using every controller feature       |
| `examples/sound_test.py`         | Speaker, headphone, mic volume tests + BT Opus streaming demo  |

```bash
python examples/basic_input.py
python examples/adaptive_triggers.py
python examples/robotics_gamepad.py
python examples/asteroid_miner.py
python examples/sound_test.py
```

---

## Games

Full pygame games that use every DualSense hardware feature simultaneously.
Requires pygame:

```bash
pip install pygame
```

### Neon Racer — Split-Screen Racing

Two-player split-screen arcade racer on a glowing neon track.

```
games/neon_racer/
```

**Controller features used:**

| Feature           | In-game use                                                              |
|-------------------|--------------------------------------------------------------------------|
| R2 adaptive       | `slope()` resistance grows with speed; `vibration()` during turbo; `off()` on oil |
| L2 adaptive       | `feedback()` normal braking; `rigid()` on wheel lock; `off()` on oil    |
| Rumble            | Wall hits, lap completion, boost pads, gravel, turbo, oil (priority queue) |
| Light bar         | HSV gradient blue→cyan→yellow→red by speed; event flashes               |
| Player LEDs       | Per-player colour assignment on race start                               |
| Mic LED           | Solid during turbo active                                                |
| Gyroscope         | Optional tilt-steering (touchpad click to toggle, blended 30%)          |
| Touchpad swipe    | Activate turbo boost                                                     |

**Keyboard fallback** — works without controllers (WASD = P1, Arrow keys = P2).

```bash
python games/neon_racer/main.py
```

See [games/neon_racer/README.md](games/neon_racer/README.md) for full details.

---

## Running Tests

```bash
# Unit tests (no hardware required)
pytest tests/unit/ -v

# Integration tests (physical controller required)
pytest tests/integration/ -v --hardware
```

---

## Documentation

Full documentation is in the [`docs/`](docs/) directory:

- [Installation](docs/installation.md) — platform setup, udev rules, pairing
- [Quick Start](docs/quickstart.md) — 5-minute guide
- [API Reference](docs/api.md) — complete class and method docs
- [HID Protocol](docs/hid_protocol.md) — byte-level BT report maps
- [Examples](docs/examples.md) — annotated example walkthroughs

---

## Platform Support

| Platform | BT | USB | Notes                                          |
|----------|----|-----|------------------------------------------------|
| Linux    | ✓  | ✓   | Requires udev rule (see Installation)          |
| Windows  | ✓  | ✓   | Standard HID driver; no ViGEm needed           |
| macOS    | ✓  | ✓   | `brew install hidapi`; grant input permissions |

---

## Dependencies

| Package     | Purpose                                       |
|-------------|-----------------------------------------------|
| `hid`       | Cross-platform HID (hidapi)                   |
| `numpy`     | Optional: IMU filtering helpers               |
| `pytest`    | Testing                                       |
| `cffi`      | Optional: Bluetooth Opus audio streaming      |
| `sounddevice` | Optional: mic-to-speaker passthrough (BT audio) |

**Bluetooth speaker streaming** additionally requires the native libopus library:

```bash
# macOS
brew install opus

# Ubuntu / Debian
sudo apt-get install libopus-dev
```

No BLE stack needed — DualSense uses **classic Bluetooth HID**.

---

## License

MIT

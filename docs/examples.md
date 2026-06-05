# Examples

This document walks through every script in the `examples/` directory.  Each
script is self-contained and can be run directly from the project root.

```bash
python examples/<script>.py
```

---

## `basic_input.py` — All inputs to the terminal

Demonstrates the simplest possible continuous read loop.  Every field of the
`InputState` is printed to one updating terminal line.

**What you see:**
```
L:(+0.01,-0.03)  R:(+0.00,+0.00)  L2:  0  R2:  0  D:NEUTRAL  Btns:[—]  Touch:—  Gyro:(+1,-2,+3)  Bat:85%
```

**Key patterns:**

```python
# Normalise raw stick values (0–255) to (−1.0 … +1.0)
nx, ny = state.left_stick.normalised()

# Collect pressed button names dynamically
pressed = [name for name in vars(state.buttons) if getattr(state.buttons, name)]

# Active touch fingers
for f in (state.touchpad.finger0, state.touchpad.finger1):
    if f.active:
        print(f"Finger {f.id}: x={f.x} y={f.y}")

# Battery
print(state.battery.level, state.battery.charging)
```

**Run:**
```bash
python examples/basic_input.py
# Ctrl-C to quit
```

---

## `rumble_demo.py` — Rumble motor patterns

Cycles through five ERM motor patterns with 1-second holds so you can feel the
difference between the two motors.

**Motor layout:**

| Parameter | Motor         | Character                  |
|-----------|---------------|----------------------------|
| `left`    | Large / LF    | Strong, low-frequency buzz |
| `right`   | Small / HF    | Light, high-frequency buzz |

**Key patterns:**

```python
# Left motor only (large, low-frequency)
ds.set_rumble(right=0, left=200)

# Right motor only (small, high-frequency)
ds.set_rumble(right=200, left=0)

# Both at full intensity
ds.set_rumble(right=255, left=255)

# Off
ds.set_rumble(0, 0)
# or equivalently:
ds.stop_rumble()
```

**Run:**
```bash
python examples/rumble_demo.py
```

---

## `adaptive_triggers.py` — Every trigger mode

Applies each `TriggerEffect` to both L2 and R2 for 2 seconds.  Press Ctrl-C
during a hold to skip to the next mode.

**Modes demonstrated:**

| Demo label          | Factory call                                             | What you feel                             |
|---------------------|----------------------------------------------------------|-------------------------------------------|
| Off                 | `TriggerEffect.off()`                                    | No resistance                             |
| Feedback (mid)      | `TriggerEffect.feedback(start=60, force=160)`            | Resistance starts at 60/255 position      |
| Weapon (pistol)     | `TriggerEffect.weapon(start=40, end=100, force=220)`     | Click at 40, then locked rigid beyond 100 |
| Vibration (engine)  | `TriggerEffect.vibration(position=0, amplitude=200, frequency=30)` | 30 Hz buzz throughout travel |
| Slope (bow tension) | `TriggerEffect.slope(start=0, end=255, start_force=0, end_force=255)` | Linear resistance ramp    |
| Rigid               | `TriggerEffect.rigid()`                                  | Maximum constant resistance               |
| Multi-pos (3 clicks)| `TriggerEffect.multi_pos([50, 120, 200], [180, 180, 180])` | Distinct clicks at three positions      |

**Key patterns:**

```python
# Apply effect to one side
ds.set_trigger_effect("right", TriggerEffect.weapon(start=40, end=100, force=220))
ds.set_trigger_effect("left",  TriggerEffect.vibration(amplitude=200, frequency=30))

# Remove effect from both triggers
ds.set_trigger_off()
```

**Run:**
```bash
python examples/adaptive_triggers.py
```

---

## `led_colors.py` — Light bar, player LEDs and mic LED demo

Four-phase LED demo covering every indicator on the controller:

1. **Rainbow sweep** — iterates HSV hue 0 → 1 in 60 steps (0.05 s each)
2. **Named colour presets** — cycles through 10 presets (0.6 s each) with RGB printed
3. **Player indicator LEDs** — shows each standard player pattern (P1–P4), all five on, then off
4. **Microphone mute LED** — demonstrates ON (solid amber), BLINK, then OFF

**Key patterns:**

```python
from pydualsense.utils.color import rgb_from_hsv, named_color
from pydualsense import PlayerLED, MicLED

# Rainbow sweep via HSV
r, g, b = rgb_from_hsv(hue, 1.0, 1.0)
ds.set_led(r, g, b)

# Named colour preset
r, g, b = named_color("orange")   # (255, 128, 0)
ds.set_led(r, g, b)

# Player indicator LEDs (symmetric PlayStation patterns)
ds.set_player_leds(PlayerLED.player(1))   # ··●··  centre dot (0x04)
ds.set_player_leds(PlayerLED.player(2))   # ·●·●·  two inner  (0x0A)
ds.set_player_leds(PlayerLED.player(3))   # ●·●·●  alternating (0x15)
ds.set_player_leds(PlayerLED.player(4))   # ●●·●●  all-but-centre (0x1B)
ds.set_player_leds(PlayerLED.ALL)         # ●●●●●  all five   (0x1F)
ds.set_player_leds(PlayerLED.NONE)        # off

# Microphone LED
ds.set_mic_led(MicLED.ON)     # solid amber
ds.set_mic_led(MicLED.BLINK)  # blinking
ds.set_mic_led(MicLED.OFF)    # off
```

**Run:**
```bash
python examples/led_colors.py
```

---

## `touchpad_viz.py` — ASCII finger position visualiser

Renders a live ASCII box to the terminal that shows up to two finger positions
scaled from the 1920 × 1080 touchpad to the terminal width × 20 rows.

**Sample output:**
```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│                     1                                                          │
│                                                                                │
│                                         2                                      │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
  Touch: YES  Click: no
```

Each active finger is shown as its tracking ID modulo 10 (`0`–`9`).  The
`Click` field reflects the physical touchpad press (not just touching).

**Key patterns:**

```python
# Iterate active fingers
for finger in state.touchpad.active_fingers:
    print(finger.id, finger.x, finger.y)

# Physical press
if state.buttons.touchpad_click:
    print("Clicked!")

# Coordinate ranges
# finger.x: 0–1919  (left → right)
# finger.y: 0–943   (top  → bottom)
```

**Run:**
```bash
python examples/touchpad_viz.py
```

---

## `motion_orientation.py` — Live gyro and accelerometer readout

Prints one updating line with:
- Gyroscope X/Y/Z in degrees per second
- Accelerometer X/Y/Z in g-force units

Rotate and tilt the controller to see the values change.

**Sample output:**
```
Gyro(°/s): X=  +12.3  Y=   -3.7  Z=   +0.1    Accel(g):  X=+0.012  Y=+0.034  Z=+1.001
```

**Key patterns:**

```python
from pydualsense.features.motion import MotionState

def on_state(state):
    ms = MotionState(gyro=state.gyro, accel=state.accel)

    gx, gy, gz = ms.gyro_dps()   # degrees per second
    ax, ay, az = ms.accel_g()    # g-force

    # Raw int16 values also available:
    # state.gyro.x  state.gyro.y  state.gyro.z
    # state.accel.x state.accel.y state.accel.z
```

**Scaling reference:**

| Sensor | Raw scale | Formula |
|--------|-----------|---------|
| Gyro   | 16.4 LSB / (°/s) | `raw / 16.4` |
| Accel  | 8192 LSB / g     | `raw / 8192` |

**Run:**
```bash
python examples/motion_orientation.py
```

---

## `robotics_gamepad.py` — Interactive terminal robotics gamepad

A fully interactive terminal UI demonstrating adaptive triggers, touchpad
visualisation, D-pad mode switching, IMU telemetry, rumble, and lightbar —
all live-rendered in a 60-column box at ~50 fps.

**Drive modes (D-Pad ↑↓←→):**

| Mode      | R2 feel                  | L2 feel         | Lightbar  | Player LEDs |
|-----------|--------------------------|-----------------|-----------|-------------|
| NORMAL    | Light feedback           | Weapon click    | Green     | P1 (centre) |
| PRECISION | Slope 0→max              | Heavy feedback  | Blue      | P2          |
| SPEED     | Engine vibration         | Weapon click    | Orange    | P3          |
| CRAWL     | Rigid wall               | Rigid wall      | Purple    | P4          |

**Controls:**

| Input        | Action                                     |
|--------------|--------------------------------------------|
| Left stick   | Forward / backward + steer                 |
| R2           | Throttle (feel changes per drive mode)     |
| L2           | Brake (weapon-click feel)                  |
| D-Pad ↑↓←→  | Switch drive mode                          |
| △ Triangle   | Cycle lightbar colour                      |
| □ Square     | Rumble burst (hold = continuous)           |
| ○ Circle     | Emergency stop (RIGID on both triggers)    |
| ✕ Cross      | Quit                                       |

**Key patterns demonstrated:**

```python
# Per-mode adaptive trigger effects
ds.set_trigger_effect("right", TriggerEffect.feedback(start=0, force=90))
ds.set_trigger_effect("right", TriggerEffect.slope(start=0, end=255, start_force=30, end_force=220))
ds.set_trigger_effect("right", TriggerEffect.vibration(position=0, amplitude=180, frequency=28))
ds.set_trigger_effect("right", TriggerEffect.rigid())

# Rising-edge detection (avoid repeat triggers on held buttons)
if state.buttons.triangle and not prev_triangle:
    ds.set_led(*next_color)
prev_triangle = state.buttons.triangle

# Differential drive with R2 boost
forward = -ny
turn    = rx
boost   = state.r2 / 255.0
speed   = 0.5 + 0.5 * boost
lw = forward * speed + turn * speed
rw = forward * speed - turn * speed
```

**Run:**
```bash
python examples/robotics_gamepad.py
```

---

## `sound_test.py` — Speaker, headphone, mic and Bluetooth audio

Tests every audio path available on the connected controller.  The script
auto-detects whether the controller is USB or Bluetooth and selects the
appropriate test set.

**USB path (controller connected via cable):**

| Test              | What it does                                                          |
|-------------------|-----------------------------------------------------------------------|
| `test_speaker`    | Ramps speaker volume 0→200, enables waveout, plays OS audio for 3 s  |
| `test_mic`        | Sets mic gain to 200, prints a prompt to speak into the controller    |
| `test_headphone`  | Ramps headphone volume 0→180, enables headphone waveout               |
| `test_headset_mic`| Checks `headphone_connected` and `mic_connected` status flags         |

**Bluetooth path:**

| Test               | What it does                                                         |
|--------------------|----------------------------------------------------------------------|
| `test_speaker_bt`  | Streams a 440 Hz Opus-encoded tone for 6 s via HID report 0x36      |
| `test_mic_bt`      | Explains the BT mic limitation; offers `source="mic"` passthrough   |

**Key patterns:**

```python
# USB: enable speaker waveout
ds.set_speaker_volume(200)
ds.enable_speaker_audio()
# play through the OS DualSense audio device here

# USB: enable headphone waveout
ds.set_headphone_volume(180)
ds.enable_headphone_audio()

# BT: stream a sine tone
stream = ds.stream_bt_speaker(source="tone", freq=440.0, duration=6.0)
time.sleep(6)
ds.stop_bt_speaker()

# BT: pipe host mic to controller speaker
stream = ds.stream_bt_speaker(source="mic")
time.sleep(5)
ds.stop_bt_speaker()

# Check jack/mic status
state = ds.read()
print("Headphone:", state.headphone_connected)
print("Mic:      ", state.mic_connected)
```

**Run:**
```bash
python examples/sound_test.py
```

**BT audio requirements:**
```bash
pip install cffi sounddevice
brew install opus          # macOS
sudo apt install libopus-dev   # Linux
```

---

## `asteroid_miner.py` — Full terminal arcade game

A complete arcade game that exercises **every** DualSense hardware feature
simultaneously.  The game runs in the terminal (80×27 lines) at 20 fps using
a background `listen_async` thread and a main game loop.

**Controller feature map:**

| Feature          | In-game use                                                   |
|------------------|---------------------------------------------------------------|
| Lightbar         | HP colour: green→yellow→pulsing red; blue when shielded       |
| Player LEDs      | Remaining lives — `PlayerLED.player(n)` symmetric patterns    |
| Mic LED          | Shield ON=solid, cooldown=BLINK, inactive=OFF                 |
| Rumble           | Collision burst; mining vibration proportional to R2          |
| R2 adaptive      | Per-weapon feel (MINE/BLAST/LASER), vibration while boosting, rigid on game-over |
| L2 adaptive      | Weapon click at brake threshold; feedback when shielded       |
| Left stick       | Move ship (wraps map edges)                                   |
| Right stick      | Aim direction (8-way, corrected for atan2 Y-axis convention)  |
| L3 click         | Toggle gyro-tilt steering                                     |
| R2 analog        | Hold near asteroid to mine (MINE weapon only)                 |
| L2 analog        | Charge shield (click feel at 30% threshold)                   |
| L1 / R1          | Rotate aim direction ±45°                                     |
| △ Triangle       | Fire (MINE=single, BLAST=3-way spread, LASER=fast piercing)   |
| ○ Circle         | Bomb — clears radius-5 around ship (8 s cooldown)             |
| □ Square hold    | Engine boost (1.8× speed, R2 vibrates)                        |
| ✕ Cross          | Quit                                                          |
| D-Pad ◄/►        | Cycle weapon: MINE → BLAST → LASER                            |
| Gyro             | Tilt-to-steer toggle via L3; X-axis tilt gauge shown on screen|
| Touchpad         | Finger 0 → target reticle `T` on map; touchpad click = homing shot |
| PS button        | Pause / unpause                                               |

**Weapon differences:**

| Weapon | Fire  | Bullet | Speed | Damage | R2 trigger feel       |
|--------|-------|--------|-------|--------|-----------------------|
| MINE   | △     | `.`    | 1.6×  | 1      | Light feedback        |
| BLAST  | △     | `B`    | 1.4×  | 1 ×3   | Heavier pull feedback |
| LASER  | △     | `\|`   | 2.8×  | 2 (piercing) | Slope build-up  |

Only the MINE weapon allows R2 proximity mining.

**Key architecture patterns:**

```python
# Background input thread + foreground game loop
ds.listen_async(_on_input)   # callback runs in daemon thread
while True:
    _tick(dt)                # physics + game logic
    _feedback(ds)            # trigger/rumble/LED updates
    _render()                # terminal draw
    time.sleep(remaining)    # maintain 20 fps

# Per-weapon adaptive trigger feel (only updates on state change)
fb_key = f"w{weapon_idx}"   # "w0", "w1", "w2"
if fb_key != prev_fb_key:
    if weapon_idx == 2:      # LASER
        ds.set_trigger_effect("right", TriggerEffect.slope(0, 200, 60, 220))
    elif weapon_idx == 1:    # BLAST
        ds.set_trigger_effect("right", TriggerEffect.feedback(30, 140))
    else:                    # MINE
        ds.set_trigger_effect("right", TriggerEffect.feedback(0, 80))

# Gyro tilt-to-steer
if gyro_steer:
    gx, gy, gz = state.gyro
    ship_x = (ship_x + gx / 12000.0) % COLS
    ship_y = (ship_y + gy / 12000.0) % ROWS

# ANSI colour rendering (standard Python, no external libs)
RST = "\033[0m"
COLORS = {'@': "\033[1;36m", '*': "\033[31m", '|': "\033[1;93m", ...}
colored_row = "  " + "  ".join(f"{COLORS.get(ch,'')}{ch}{RST}" for ch in row)
```

**Run:**
```bash
python examples/asteroid_miner.py
```

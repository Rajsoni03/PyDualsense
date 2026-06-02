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

## `led_colors.py` — Rainbow sweep and named colour presets

Three-phase light bar demo:

1. **Rainbow sweep** — iterates HSV hue 0 → 1 in 60 steps (0.05 s per step)
2. **Named presets** — shows each colour for 0.6 s with its RGB values printed
3. **Player colours** — cycles through the four default player colours

**Key patterns:**

```python
from pydualsense.utils.color import rgb_from_hsv, named_color

# Compute a colour from hue/saturation/value (all 0–1)
r, g, b = rgb_from_hsv(hue, 1.0, 1.0)
ds.set_led(r, g, b)

# Use a named preset
r, g, b = named_color("orange")   # (255, 128, 0)
ds.set_led(r, g, b)

# Available names:
# red, green, blue, white, off, yellow, cyan, magenta,
# orange, purple, pink, player1, player2, player3, player4
```

**Run:**
```bash
python examples/led_colors.py
```

---

## `touchpad_viz.py` — ASCII finger position visualiser

Renders a live ASCII box to the terminal that shows up to two finger positions
scaled from the 1920 × 943 touchpad to the terminal width × 20 rows.

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

## `robotics_gamepad.py` — Differential-drive robot mapping

A template for driving a robot with the DualSense controller.  Adapt the
`drive()` stub to your actual motor interface (ROS publisher, serial command,
GPIO PWM, etc.).

**Control mapping:**

| Input              | Robot action                          |
|--------------------|---------------------------------------|
| Left stick Y       | Forward / backward speed (−1 … +1)    |
| Right stick X      | Turn rate (left / right, −1 … +1)     |
| R2 analog          | Boost multiplier (0 = 50%, 1 = 100%)  |
| Circle button      | Emergency stop                        |
| Triangle button    | Toggle LED indicator                  |

**Differential drive math:**

```python
# After deadzone and normalisation:
forward = -ny          # stick up = positive forward
turn    = rx
boost   = state.r2 / 255.0          # 0.0 … 1.0

speed = 0.5 + 0.5 * boost           # 50–100 % speed range

left_wheel  = (forward + turn) * speed
right_wheel = (forward - turn) * speed
```

**Key patterns demonstrated:**

```python
# Circular deadzone (recommended for sticks)
from pydualsense.utils.deadzone import apply_deadzone_circular
nx, ny = state.left_stick.normalised()
nx, ny = apply_deadzone_circular(nx, ny, threshold=0.10)

# R2 analog as a continuous 0–1 value
boost = state.r2 / 255.0

# Emergency stop on button press
if state.buttons.circle:
    drive(0.0, 0.0)
```

> **Note:** The `drive()` function in this script is a stub that does nothing.
> Replace it with calls to your actual robot driver.  The comment in the
> source shows the left/right wheel values you would forward to the motors.

**Run:**
```bash
python examples/robotics_gamepad.py
```

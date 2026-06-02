# Quick Start

This guide gets you from zero to a working controller session in five minutes.

## Prerequisites

1. Controller paired and connected (see [Installation](installation.md))
2. `pip install hid` completed
3. Library installed: `pip install -e .` from the project root

---

## Step 1 — Verify discovery

```python
from pydualsense.transport.discovery import list_controllers

controllers = list_controllers()
print(controllers)
# [DualSense [Sony Wireless Controller] VID=0x054c PID=0x0ce6 serial='...']
```

If the list is empty, the controller is not connected or the udev rule is
missing (Linux only — see [Installation](installation.md)).

---

## Step 2 — Read controller state

```python
from pydualsense import DualSense

ds = DualSense()
ds.connect()

state = ds.read()

print("Left stick:", state.left_stick.normalised())   # (-1.0 … +1.0, -1.0 … +1.0)
print("L2 analog: ", state.l2)                         # 0–255
print("Cross:     ", state.buttons.cross)              # True/False
print("D-pad:     ", state.dpad.name)                  # N / NE / E …
print("Battery:   ", state.battery.level, "%")

ds.disconnect()
```

---

## Step 3 — Control outputs

```python
from pydualsense import DualSense, PlayerLED

with DualSense() as ds:          # auto-connects and disconnects

    # Light bar colour
    ds.set_led(255, 0, 0)        # red
    ds.set_led(0, 0, 255)        # blue

    # Player indicator LEDs
    ds.set_player_leds(PlayerLED.player(1))   # one dot = player 1

    # Rumble (right = small/HF, left = large/LF)
    import time
    ds.set_rumble(right=200, left=100)
    time.sleep(0.5)
    ds.stop_rumble()
```

---

## Step 4 — Adaptive triggers

```python
from pydualsense import DualSense
from pydualsense.features.triggers import TriggerEffect
import time

with DualSense() as ds:
    # Weapon mode on right trigger: feels like a gun trigger
    ds.set_trigger_effect("right", TriggerEffect.weapon(start=40, end=100, force=220))
    time.sleep(3)

    # Vibration mode on left trigger: feels like an engine
    ds.set_trigger_effect("left", TriggerEffect.vibration(amplitude=200, frequency=30))
    time.sleep(3)

    # Turn off all effects
    ds.set_trigger_off()
```

---

## Step 5 — Continuous event loop

```python
from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState

def on_state(state: InputState):
    # Called ~250 times per second over BT
    ls = state.left_stick.normalised()

    if state.buttons.circle:
        print("Circle!")

    if state.buttons.ps:
        print("PS button — quitting")
        raise KeyboardInterrupt   # stop the loop

ds = DualSense()
ds.connect()
ds.listen(on_state)     # blocks until Ctrl-C or exception
ds.disconnect()
```

---

## Step 6 — Background thread

```python
from pydualsense import DualSense
import time

ds = DualSense()
ds.connect()

def on_state(state):
    if state.buttons.triangle:
        ds.set_led(0, 255, 0)     # green when triangle held
    else:
        ds.set_led(0, 0, 255)     # blue otherwise

ds.listen_async(on_state)

# Your main thread is free to do other work
time.sleep(10)

ds.stop()
ds.disconnect()
```

---

## Touchpad

```python
def on_state(state):
    for finger in state.touchpad.active_fingers:
        # x: 0–1919,  y: 0–1079
        print(f"Finger {finger.id}: ({finger.x}, {finger.y})")

    if state.buttons.touchpad_click:
        print("Touchpad clicked!")
```

---

## Motion sensors

```python
from pydualsense.features.motion import MotionState

def on_state(state):
    ms = MotionState(gyro=state.gyro, accel=state.accel)
    gx, gy, gz = ms.gyro_dps()       # degrees per second
    ax, ay, az = ms.accel_g()        # g-force
    print(f"Gyro: {gx:+.1f}°/s  Accel Z: {az:+.3f}g")
```

---

## Deadzone handling

Raw analog sticks have a mechanical deadzone near centre.  Use the helpers:

```python
from pydualsense.utils.deadzone import apply_deadzone_circular

def on_state(state):
    nx, ny = state.left_stick.normalised()
    nx, ny = apply_deadzone_circular(nx, ny, threshold=0.10)
    # Now (0, 0) when stick is in the centre 10% of travel
```

---

## Named colours

```python
from pydualsense.utils.color import named_color, rgb_from_hsv

r, g, b = named_color("orange")
ds.set_led(r, g, b)

# Or compute from HSV (hue 0–1, saturation 0–1, value 0–1)
r, g, b = rgb_from_hsv(0.3, 1.0, 1.0)
ds.set_led(r, g, b)
```

Available names: `red`, `green`, `blue`, `white`, `off`, `yellow`, `cyan`,
`magenta`, `orange`, `purple`, `pink`, `player1`–`player4`.

---

## Next steps

- [API Reference](api.md) — complete method and class documentation
- [HID Protocol](hid_protocol.md) — raw byte maps for advanced use
- [Examples](examples.md) — annotated walkthrough of all example scripts

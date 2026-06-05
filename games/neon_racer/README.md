# Neon Racer

A two-player split-screen arcade racing game built with pygame and the
PyDualsenseBT library.  Race across 3 laps on a glowing neon track with
full DualSense hardware integration — adaptive triggers, haptic rumble,
light bar, gyro steering, and more.

---

## Requirements

- Python 3.12 (recommended; 3.14 has a known `pygame.font` import issue)
- `pygame` 2.x
- `hid` (for controller support)

```bash
pip install pygame hid
```

---

## Running

```bash
# From the project root
python games/neon_racer/main.py
```

Keyboard fallback is always active — no controllers required.

---

## Controls

### Keyboard

| Action        | Player 1  | Player 2    |
|---------------|-----------|-------------|
| Throttle      | W         | ↑           |
| Brake/Reverse | S         | ↓           |
| Steer left    | A         | ←           |
| Steer right   | D         | →           |
| Turbo         | Shift     | Right Ctrl  |
| Pause         | Escape    | —           |

### DualSense Controller

| Input           | Action                                    |
|-----------------|-------------------------------------------|
| R2 analog       | Throttle                                  |
| L2 analog       | Brake / reverse                           |
| Left stick X    | Steer                                     |
| Touchpad swipe  | Activate turbo boost                      |
| Touchpad click  | Toggle gyro tilt-steering                 |
| Options         | Pause / resume                            |
| Cross (✕)       | Ready (menu) / return to menu (results)   |
| Options (paused)| Resume race                               |
| Cross (paused)  | Quit to desktop                           |

---

## Controller Features

| Hardware Feature  | In-game use                                                             |
|-------------------|-------------------------------------------------------------------------|
| **R2 adaptive**   | `slope()` resistance scales with speed; `vibration()` during turbo; `off()` on oil |
| **L2 adaptive**   | `feedback()` normal braking; `rigid()` on wheel lock; `off()` on oil   |
| **Rumble**        | Priority queue: wall hit > lap > boost > gravel > turbo > oil           |
| **Light bar**     | HSV gradient blue→cyan→yellow→red by speed; event flashes              |
| **Player LEDs**   | Set to player colour (cyan / magenta) on race start                     |
| **Mic LED**       | Solid amber while turbo is active                                       |
| **Gyroscope**     | Tilt-to-steer (toggle via touchpad click; 30 % blend with stick input)  |
| **Touchpad**      | Swipe = turbo; click = gyro mode toggle                                 |

---

## Track

The track is a smooth closed loop defined by 16 waypoints and interpolated
with a Catmull-Rom spline (~384 points).  World size: 2400 × 1600 units.

### Surface zones

| Surface  | Effect                                                  |
|----------|---------------------------------------------------------|
| Road     | Standard friction and top speed                         |
| Gravel   | Reduced grip and max speed; gravel haptic rumble        |
| Boost    | +15 % speed burst on entry; white LED flash             |
| Oil      | Low friction (understeer); L2/R2 set to `off()`; oil rumble |

### Lap validation

A lap is only counted valid if the car has crossed **all 4 checkpoints**
before crossing the start/finish line.  Cutting corners by going off-track
does not count.

---

## Architecture

```
games/neon_racer/
├── main.py              # pygame init, main loop, DT capping
├── game.py              # GameStateMachine (MENU/COUNTDOWN/RACING/PAUSED/RESULTS)
├── car.py               # Arcade-physics Car, turbo, lap tracking
├── track.py             # Spline, boundary polygons, surface detection, collision
├── renderer.py          # Split-screen cameras, HUD, neon draw
├── effects.py           # ParticleSystem, glow draw helpers, camera transform
├── controller_bridge.py # ControllerPlayer/KeyboardPlayer, HapticManager
├── constants.py         # Physics tuning, color presets, enums
└── README.md            # This file
```

### Key tuning constants (`constants.py`)

| Constant           | Default | Notes                            |
|--------------------|---------|----------------------------------|
| `MAX_SPEED`        | 320     | world units / second             |
| `ACCELERATION`     | 280     | units / s²                       |
| `BRAKE_FORCE`      | 420     | units / s²                       |
| `TURBO_MULTIPLIER` | 1.42    | speed cap multiplier             |
| `TURBO_DURATION`   | 3.0 s   |                                  |
| `TURBO_COOLDOWN`   | 8.0 s   |                                  |
| `TRACK_WIDTH`      | 130     | world units                      |
| `TOTAL_LAPS`       | 3       |                                  |
| `FPS`              | 60      |                                  |

---

## Performance notes

- Particle system uses direct `pygame.draw` calls (no per-particle Surface
  allocation).
- Trigger HID output is gated by `speed_bucket` (8 quantised levels) to
  avoid flooding the controller with redundant writes every frame.
- Track boundary edges are precomputed in `Track.__init__` — not rebuilt
  per physics step.

# Neon Racer — Split-Screen Game Plan

## Concept
Two-player local split-screen top-down racing game.  
Each player uses one DualSense controller.  
Neon aesthetic — glowing track lines, particle trails, color-shifted LEDs.  
First to complete **3 laps** wins.

---

## File Structure

```
examples/neon_racer/
├── main.py               # Entry point: pygame init, controller connect, game loop
├── game.py               # GameStateMachine: MENU → CONNECTING → COUNTDOWN → RACE → RESULTS
├── car.py                # Car entity: arcade physics, surface interaction, turbo
├── track.py              # Track: spline waypoints, surface zones, lap detection
├── controller_bridge.py  # DualSense input → CarInput; haptic/LED output per frame
├── renderer.py           # Split-screen viewports, neon glow, HUD overlay
├── effects.py            # ParticleSystem, GlowLayer
└── constants.py          # Colors, window size, physics tuning, surface definitions
```

---

## Game States

| State        | Description                                                   |
|--------------|---------------------------------------------------------------|
| `MENU`       | Neon logo, "Press X to ready up" per player                   |
| `CONNECTING` | Wait for 2 DualSense controllers, show connect status         |
| `COUNTDOWN`  | 3 → 2 → 1 → GO! with rumble pulse on each beat               |
| `RACING`     | Main race loop — 3 laps, split-screen live                    |
| `RESULTS`    | Winner banner, lap times, "Press X to rematch / Options to quit" |

---

## Car Physics (`car.py`)

| Property      | Details                                                         |
|---------------|-----------------------------------------------------------------|
| Position      | (x, y) float world coords                                       |
| Heading       | angle in degrees, 0 = right                                     |
| Speed         | scalar float, 0 – MAX_SPEED                                     |
| Acceleration  | R2 analog (0–255) → force applied along heading                 |
| Braking       | L2 analog (0–255) → reverse force; locks wheels above threshold |
| Steering      | Left stick X → heading delta, scaled by speed (tighter at high speed) |
| Gyro steering | Optional: controller tilt (accel.x) replaces/blends with stick  |
| Friction      | Constant speed decay every frame (surface-dependent)            |
| Turbo         | 1.4× speed multiplier, 3 s duration, 8 s cooldown              |
| Wall bounce   | On track boundary collision: reflect velocity, 30% speed loss   |

---

## Track (`track.py`)

### Structure
- Closed-loop defined by **waypoint list** (spline-interpolated)
- Track width: 120 px world units
- Total laps: 3

### Surface Zones
| Zone        | Color            | Effect on Car                       | Haptic Effect              |
|-------------|------------------|--------------------------------------|----------------------------|
| Normal road | Dark gray        | Standard friction                    | None                       |
| Gravel      | Orange/brown     | 2× friction, 0.8× max speed         | Continuous low rumble      |
| Boost pad   | Cyan glow strips | Instant +30% speed burst            | 200 ms strong right rumble |
| Oil slick   | Translucent green| 0.15× friction (slides freely)       | Soft left rumble loop      |

### Lap Detection
- Checkpoint line across track start/finish
- Car must pass all mid-track checkpoints before lap counts (anti-cut)
- On lap complete: LED pulse + medium rumble burst (300 ms)

---

## Controller Mapping (`controller_bridge.py`)

### Input
| Controller Input     | Game Action                          |
|----------------------|--------------------------------------|
| Left stick X         | Steering (primary)                   |
| Gyro accel.x         | Optional tilt steering (blended)     |
| R2 analog (0–255)    | Accelerate                           |
| L2 analog (0–255)    | Brake                                |
| Touchpad swipe up    | Activate turbo                       |
| Cross (×)            | Confirm / restart in menus           |
| Options              | Pause                                |
| D-pad                | Menu navigation                      |
| Touchpad click       | Toggle gyro steering on/off          |

### Adaptive Trigger Effects (R2 — Accelerate)

| Condition              | Effect                                               |
|------------------------|------------------------------------------------------|
| Normal driving         | `TriggerEffect.slope(start=0, end=255, start_force=10, end_force=int(speed/MAX_SPEED * 200))` — resistance grows with speed |
| At top speed           | `TriggerEffect.slope(..., end_force=255)` — engine ceiling feel |
| Turbo active           | `TriggerEffect.vibration(position=0, amplitude=80, frequency=28)` — engine buzz |
| On oil slick           | `TriggerEffect.off()` — pedal sinks, no grip         |

### Adaptive Trigger Effects (L2 — Brake)

| Condition              | Effect                                               |
|------------------------|------------------------------------------------------|
| Normal braking         | `TriggerEffect.feedback(start=25, force=140)`        |
| Hard brake (ABS lock)  | `TriggerEffect.rigid()` — max resistance, locked feel |
| On oil slick           | `TriggerEffect.off()` — no braking grip              |

### Rumble Events

| Event                  | Left motor | Right motor | Duration  |
|------------------------|-----------|-------------|-----------|
| Gravel surface         | 70         | 50          | Continuous|
| Boost pad hit          | 0          | 210         | 200 ms    |
| Wall collision         | 190        | 200         | 180 ms    |
| Lap complete           | 100        | 160         | 350 ms    |
| Turbo active           | 40         | 90          | Continuous|
| Oil slick              | 30         | 0           | Continuous|
| Countdown beat (3,2,1) | 120        | 120         | 120 ms    |
| GO! signal             | 220        | 220         | 250 ms    |
| Finish line cross      | 255        | 255         | 500 ms    |

### LED Light Bar

| Condition              | Color                                                |
|------------------------|------------------------------------------------------|
| Idle / menu            | P1 = Cyan `(0,220,255)`, P2 = Magenta `(255,0,220)` |
| Speed gradient         | HSV shift: Blue(0%) → Cyan(40%) → Yellow(70%) → Red(100%) |
| Boost pad hit          | Pure white flash `(255,255,255)`, 200 ms            |
| Lap complete           | Bright flash of player color, 400 ms               |
| Wall collision         | White flash `(255,100,100)`, 150 ms                 |
| Turbo active           | Fast pulse of player color                          |
| Winner                 | Rapid rainbow cycle                                 |
| Loser                  | Dim pulse then fade to off                          |

### Player Indicator LEDs

| Player | Pattern              |
|--------|----------------------|
| P1     | `PlayerLED.player(1)` — center dot        |
| P2     | `PlayerLED.player(2)` — two symmetrical   |

### Mic LED

| Condition         | State        |
|-------------------|--------------|
| Turbo on cooldown | `MicLED.BLINK` |
| Turbo ready       | `MicLED.ON`    |
| Turbo active      | `MicLED.OFF`   |

---

## Rendering (`renderer.py`)

### Split Screen
- Window: **1280 × 720**
- Left half `(0–639)`: Player 1 viewport
- Right half `(640–1279)`: Player 2 viewport
- Center divider: 2 px neon white line

### Camera
- Each viewport follows its own car (car-centered)
- Camera rotates so car always points up (forward-facing camera)
- Smooth lerp to car position (no snapping)

### Neon Glow Effect
- Track borders and center line rendered twice:
  1. Wide blurred pass (via `pygame.transform.smoothscale` trick) — glow halo
  2. Sharp thin line on top — bright core
- Car: colored rectangle + glow halo matching player LED color
- Boost pads: animated scan-line strips (scrolling UV offset each frame)

### Particle Trail
- Each car emits speed-scaled particles behind it
- Particle color = current LED color
- Particles fade out over 0.4 s with scale-down
- On boost: 2× particle count, white/cyan burst

### HUD (per split half)
```
┌─────────────────────────────┐
│  LAP  2 / 3    Δ +1.2 s    │
│  ████████░░  SPEED  187     │
│  [■■■■■░░░░] TURBO          │
└─────────────────────────────┘
```
- Speed bar: arc gauge, neon fill
- Lap counter: top-left
- Delta to opponent: top-right (green if ahead, red if behind)
- Turbo bar: fills over cooldown time, pulses when ready

---

## Implementation Phases & ToDo Tasks

### Phase 1 — Foundation
- [ ] `constants.py` — all colors, sizes, physics values, surface enums
- [ ] `car.py` — Car class with full physics step
- [ ] `track.py` — waypoints, spline build, surface zone polygons, lap detection
- [ ] `main.py` — pygame window, keyboard-only test loop (no controllers yet)

### Phase 2 — Rendering
- [ ] `renderer.py` — split viewport setup, camera transform, track draw
- [ ] `effects.py` — GlowLayer (double-pass), ParticleSystem
- [ ] `renderer.py` — HUD overlay (speed, laps, delta, turbo bar)

### Phase 3 — Controller Integration
- [ ] `controller_bridge.py` — connect 2 controllers, read input per frame
- [ ] Map sticks/triggers/buttons to CarInput dataclass
- [ ] Adaptive trigger updates per frame (speed-based slope, surface overrides)
- [ ] Rumble event queue with timed duration
- [ ] LED speed gradient update per frame
- [ ] Mic LED turbo state sync

### Phase 4 — Game Flow
- [ ] `game.py` — GameStateMachine with all state transitions
- [ ] MENU state: neon logo, ready-up per player
- [ ] COUNTDOWN state: 3-2-1-GO with rumble + LED flash
- [ ] RACING state: wire everything together
- [ ] RESULTS state: winner banner, lap times, rematch prompt

### Phase 5 — Polish
- [ ] Gyro steering blend (touchpad click toggle)
- [ ] All surface zone effects (gravel, boost, oil) — haptics + visuals
- [ ] Turbo complete (touchpad swipe detection, visual + haptic)
- [ ] LED rainbow winner effect
- [ ] Fine-tune physics constants for fun handling feel
- [ ] Graceful disconnect handling (pause + reconnect prompt)

---

## Dependencies

```
pygame >= 2.1
hid      (already in project)
pydualsense (this project)
```

Install:
```bash
pip install pygame
```

---

## Key Design Decisions

1. **Keyboard fallback**: If fewer than 2 controllers connected, allow keyboard
   control (WASD + arrow keys) so game is testable without hardware.

2. **Trigger update rate**: Adaptive trigger effects are sent only when the
   relevant value changes (speed bucket changes) — not every frame — to avoid
   flooding HID output.

3. **Haptic queue**: Timed events (wall hit, lap, boost) are stored in a priority
   queue; only the highest-priority active event drives the rumble motors each
   frame. Prevents conflicting rumble commands.

4. **Gyro steering**: Accel X axis, low-pass filtered. Blended 30% gyro / 70%
   stick by default. Touchpad click toggles to 100% gyro mode.

5. **Track format**: Waypoints defined as a Python list of (x, y) tuples.
   Spline built at startup. Surface zones are convex polygons tested with
   point-in-polygon each physics step.

"""
Neon Racer — Car entity with arcade physics.
"""

import math
from dataclasses import dataclass, field
from typing import Tuple

from constants import (
    MAX_SPEED, ACCELERATION, BRAKE_FORCE, FRICTION,
    STEER_RATE, STEER_SPEED_DIV, REVERSE_MAX, WHEEL_LOCK_SPEED,
    TURBO_MULTIPLIER, TURBO_DURATION, TURBO_COOLDOWN,
    WALL_BOUNCE_LOSS, GYRO_BLEND, GYRO_SCALE, DEADZONE,
    SURFACE_FRICTION, SURFACE_MAX_SPEED, Surface, PLAYER_COLORS,
)


@dataclass
class CarInput:
    """Normalised input values for one car, from controller or keyboard."""
    throttle:  float = 0.0   # 0–1   (R2 analog or W key)
    brake:     float = 0.0   # 0–1   (L2 analog or S key)
    steer:     float = 0.0   # -1 left … +1 right (stick X or A/D keys)
    gyro_x:    float = 0.0   # raw accelerometer X for tilt steering
    turbo:     bool  = False  # touchpad swipe or shift key
    gyro_mode: bool  = False  # touchpad click toggle


class Car:
    """
    Arcade-physics car.

    World coordinates: X right, Y down.
    Heading: 0° = right, 90° = down, etc. (pygame convention).
    """

    def __init__(self, x: float, y: float, heading: float,
                 player_index: int):
        self.x       = x
        self.y       = y
        self.heading = heading      # degrees
        self.speed   = 0.0          # world units / second (positive = forward)

        self.player_index = player_index
        self.color        = PLAYER_COLORS[player_index]

        # Surface state
        self.surface       = Surface.ROAD
        self._last_surface = Surface.ROAD

        # Turbo
        self.turbo_active   = False
        self.turbo_timer    = 0.0   # time remaining while active
        self.turbo_cooldown = 0.0   # cooldown remaining after use
        self._turbo_pressed_last = False

        # Gyro steering toggle
        self.gyro_mode  = False
        self._last_brake = 0.0

        # Lap tracking (managed by track)
        self.lap          = 0
        self.checkpoints  = set()   # checkpoint IDs passed this lap
        self.lap_times: list[float] = []
        self.lap_start    = 0.0
        self.finished     = False

        # Collision flash timer (for renderer)
        self.hit_flash    = 0.0

        # Speed-bucket for trigger updates (avoids flooding HID output)
        self._last_speed_bucket = -1

    # ── Physics step ─────────────────────────────────────────────────────────

    def update(self, inp: CarInput, dt: float) -> None:
        if self.finished:
            # Slow to stop on finish
            self.speed = max(0.0, self.speed - FRICTION * 3 * dt)
            return

        self._handle_turbo(inp, dt)
        self._apply_steering(inp, dt)
        self._apply_throttle_brake(inp, dt)
        self._apply_friction(dt)
        self._move(dt)

        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

    def _handle_turbo(self, inp: CarInput, dt: float) -> None:
        # Edge-trigger on turbo input
        turbo_pressed = inp.turbo and not self._turbo_pressed_last
        self._turbo_pressed_last = inp.turbo

        if self.turbo_active:
            self.turbo_timer -= dt
            if self.turbo_timer <= 0:
                self.turbo_active   = False
                self.turbo_cooldown = TURBO_COOLDOWN
        elif self.turbo_cooldown > 0:
            self.turbo_cooldown -= dt
        elif turbo_pressed and self.turbo_cooldown <= 0:
            self.turbo_active = True
            self.turbo_timer  = TURBO_DURATION

        # Gyro mode toggle
        if inp.gyro_mode and not self._turbo_pressed_last:
            self.gyro_mode = not self.gyro_mode

    def _apply_steering(self, inp: CarInput, dt: float) -> None:
        steer = inp.steer

        if self.gyro_mode and abs(inp.gyro_x) > 0.01:
            tilt = inp.gyro_x * GYRO_SCALE * 60   # scale to per-second
            steer = steer * (1 - GYRO_BLEND) + tilt * GYRO_BLEND

        steer = _clamp(steer, -1.0, 1.0)

        if abs(steer) < DEADZONE:
            steer = 0.0
        else:
            steer = (steer - math.copysign(DEADZONE, steer)) / (1.0 - DEADZONE)

        speed_factor = 1.0 + abs(self.speed) / (MAX_SPEED * STEER_SPEED_DIV)
        delta = STEER_RATE * steer * dt / speed_factor

        if abs(self.speed) > 1.0:
            self.heading += delta

    def _apply_throttle_brake(self, inp: CarInput, dt: float) -> None:
        surf_max = MAX_SPEED * SURFACE_MAX_SPEED[self.surface]
        if self.turbo_active:
            surf_max *= TURBO_MULTIPLIER

        # Throttle
        if inp.throttle > 0.01:
            force = ACCELERATION * inp.throttle
            self.speed = min(self.speed + force * dt, surf_max)

        # Brake / reverse
        if inp.brake > 0.01:
            if self.speed > WHEEL_LOCK_SPEED:
                self.speed -= BRAKE_FORCE * inp.brake * dt
            elif self.speed > 0.5:
                self.speed = max(0.0, self.speed - BRAKE_FORCE * inp.brake * dt)
            else:
                # Reverse
                self.speed = max(-REVERSE_MAX, self.speed - ACCELERATION * 0.5 * inp.brake * dt)

    def _apply_friction(self, dt: float) -> None:
        if self.speed == 0:
            return
        friction = FRICTION * SURFACE_FRICTION[self.surface] * dt
        if self.speed > 0:
            self.speed = max(0.0, self.speed - friction)
        else:
            self.speed = min(0.0, self.speed + friction)

    def _move(self, dt: float) -> None:
        rad = math.radians(self.heading)
        self.x += math.cos(rad) * self.speed * dt
        self.y += math.sin(rad) * self.speed * dt

    # ── Wall collision ────────────────────────────────────────────────────────

    def wall_bounce(self, normal_angle: float) -> None:
        """Reflect heading off a wall with given normal angle (degrees)."""
        self.speed     *= (1.0 - WALL_BOUNCE_LOSS)
        # Reflect heading around the normal
        incident       = self.heading
        self.heading   = 2 * normal_angle - incident + 180
        self.hit_flash = 0.15   # seconds

    def push_back(self, dx: float, dy: float) -> None:
        """Nudge car out of a wall overlap."""
        self.x += dx
        self.y += dy

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @property
    def speed_frac(self) -> float:
        """Speed as 0–1 fraction of MAX_SPEED."""
        return _clamp(abs(self.speed) / MAX_SPEED, 0.0, 1.0)

    @property
    def turbo_ready(self) -> bool:
        return self.turbo_cooldown <= 0 and not self.turbo_active

    @property
    def turbo_frac(self) -> float:
        """Turbo bar fill: 0 = empty/active, 1 = fully recharged."""
        if self.turbo_active:
            return self.turbo_timer / TURBO_DURATION
        return _clamp(1.0 - self.turbo_cooldown / TURBO_COOLDOWN, 0.0, 1.0)

    @property
    def speed_bucket(self) -> int:
        """Speed quantised to 8 buckets — used to avoid redundant HID writes."""
        return int(self.speed_frac * 8)

    @property
    def is_braking_hard(self) -> bool:
        return self.speed > WHEEL_LOCK_SPEED * 2 and self._last_brake > 0.7

    def set_surface(self, surface: Surface) -> None:
        self.surface = surface

    # ── Lap helpers (called by Track) ─────────────────────────────────────────

    def pass_checkpoint(self, cp_id: int) -> None:
        self.checkpoints.add(cp_id)

    def complete_lap(self, total_checkpoints: int, elapsed: float) -> bool:
        """Returns True if this constitutes a valid lap completion."""
        if len(self.checkpoints) < total_checkpoints:
            return False
        self.checkpoints.clear()
        lap_time = elapsed - self.lap_start
        self.lap_times.append(lap_time)
        self.lap_start = elapsed
        self.lap += 1
        return True

    def set_input_cache(self, inp: CarInput) -> None:
        self._last_brake = inp.brake


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

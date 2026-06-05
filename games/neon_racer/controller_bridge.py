"""
Neon Racer — DualSense controller bridge.

Manages up to 2 DualSense controllers, reads input into CarInput dataclasses,
and drives all haptic/LED output (adaptive triggers, rumble, light bar, LEDs).
"""

import sys
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Add project root so pydualsense can be imported
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from pydualsense import DualSense
    from pydualsense.features.triggers import TriggerEffect
    from pydualsense.protocol.constants import PlayerLED, MicLED
    HAVE_CONTROLLERS = True
except Exception:
    HAVE_CONTROLLERS = False

from car import Car, CarInput
from constants import (
    MAX_SPEED, RUMBLE, HAPTIC_PRIORITY, Surface,
    PLAYER_COLORS,
)
from renderer import speed_to_led_color


# ── Haptic event ──────────────────────────────────────────────────────────────

@dataclass
class HapticEvent:
    name:      str
    right_m:   int
    left_m:    int
    duration:  float   # 0.0 = continuous (fires every frame while queued)
    priority:  int
    timer:     float = field(init=False)

    def __post_init__(self):
        self.timer = self.duration

    @property
    def expired(self) -> bool:
        return self.duration > 0 and self.timer <= 0

    def tick(self, dt: float) -> None:
        if self.duration > 0:
            self.timer -= dt


# ── Per-player haptic state ───────────────────────────────────────────────────

class HapticManager:
    """Priority queue of haptic events for one controller."""

    def __init__(self):
        self._events: List[HapticEvent] = []
        self._continuous: Optional[HapticEvent] = None   # surface-driven

    def push(self, name: str) -> None:
        r, l, dur = RUMBLE[name]
        pri = HAPTIC_PRIORITY.get(name, 0)
        evt = HapticEvent(name, int(r), int(l), dur, pri)
        if dur == 0.0:
            # Continuous — replace if higher priority
            if self._continuous is None or pri >= self._continuous.priority:
                self._continuous = evt
        else:
            # One-shot — skip if same name already active
            if any(e.name == name for e in self._events):
                return
            self._events.append(evt)
            self._events.sort(key=lambda e: -e.priority)

    def clear_continuous(self) -> None:
        self._continuous = None

    def update(self, dt: float) -> Tuple[int, int]:
        """Returns (right_motor, left_motor) for this frame."""
        for e in self._events:
            e.tick(dt)
        self._events = [e for e in self._events if not e.expired]

        active_one_shot = self._events[0] if self._events else None

        if active_one_shot and (self._continuous is None or
                                active_one_shot.priority >= self._continuous.priority):
            return active_one_shot.right_m, active_one_shot.left_m
        elif self._continuous:
            return self._continuous.right_m, self._continuous.left_m
        return 0, 0


# ── Touchpad swipe detector ───────────────────────────────────────────────────

class TouchpadSwipeDetector:
    def __init__(self):
        self._prev_y: Optional[float] = None
        self._prev_click: bool = False

    def update(self, state) -> Tuple[bool, bool]:
        """Returns (swipe_up, click_edge)."""
        swipe_up   = False
        click_edge = False

        try:
            tp = state.touchpad
            fingers = tp.fingers
            click   = tp.clicked

            # Click edge detect
            if click and not self._prev_click:
                click_edge = True
            self._prev_click = click

            # Swipe up: track first active finger moving upward
            if fingers:
                f = fingers[0]
                if f.active:
                    # Touchpad Y: 0 = top, 1079 = bottom
                    norm_y = f.y / 1079.0
                    if self._prev_y is not None:
                        dy = self._prev_y - norm_y   # positive = moved up
                        if dy > 0.15:
                            swipe_up = True
                    self._prev_y = norm_y
                else:
                    self._prev_y = None
            else:
                self._prev_y = None

        except AttributeError:
            pass

        return swipe_up, click_edge


# ── Single controller player ──────────────────────────────────────────────────

class ControllerPlayer:
    """Wraps one DualSense; produces CarInput and consumes haptic commands."""

    def __init__(self, ds: "DualSense", player_idx: int):
        self.ds          = ds
        self.player_idx  = player_idx
        self.haptics     = HapticManager()
        self.swipe       = TouchpadSwipeDetector()
        self._last_speed_bucket = -1
        self._last_surface: Optional[Surface] = None
        self._last_turbo   = False
        self._led_flash_timer = 0.0
        self._led_flash_color: Optional[Tuple[int,int,int]] = None
        self._rainbow_phase = 0.0
        self._winner = False
        self._base_color = PLAYER_COLORS[player_idx]

        # Setup player LEDs
        try:
            ds.set_player_leds(PlayerLED.player(player_idx + 1))
        except Exception:
            pass

    def read_input(self) -> CarInput:
        try:
            state = self.ds.state
            if state is None:
                return CarInput()

            # Sticks — normalise to -1…+1
            steer    = (state.left_stick.x - 128) / 128.0
            throttle = state.r2 / 255.0
            brake    = state.l2 / 255.0

            # Gyro accel X (raw int16)
            gyro_x = getattr(state.accel, "x", 0) / 8192.0

            # Touchpad
            swipe_up, click_edge = self.swipe.update(state)

            # Buttons
            try:
                options_btn = state.buttons.options
                cross_btn   = state.buttons.cross
            except AttributeError:
                options_btn = False
                cross_btn   = False

            return CarInput(
                throttle=float(max(0, min(1, throttle))),
                brake=float(max(0, min(1, brake))),
                steer=float(max(-1, min(1, steer))),
                gyro_x=float(gyro_x),
                turbo=swipe_up,
                gyro_mode=click_edge,
            )
        except Exception:
            return CarInput()

    def is_options_pressed(self) -> bool:
        try:
            return bool(self.ds.state.buttons.options)
        except Exception:
            return False

    def is_cross_pressed(self) -> bool:
        try:
            return bool(self.ds.state.buttons.cross)
        except Exception:
            return False

    def update_output(self, car: Car, dt: float) -> None:
        self._update_haptics(car, dt)
        self._update_triggers(car)
        self._update_led(car, dt)
        self._update_mic_led(car)

    def _update_haptics(self, car: Car, dt: float) -> None:
        # Continuous surface events
        self.haptics.clear_continuous()
        if car.surface == Surface.GRAVEL:
            self.haptics.push("gravel")
        elif car.surface == Surface.OIL:
            self.haptics.push("oil")
        elif car.turbo_active:
            self.haptics.push("turbo")

        right_m, left_m = self.haptics.update(dt)
        try:
            self.ds.set_rumble(right_m, left_m)
        except Exception:
            pass

    def _update_triggers(self, car: Car) -> None:
        bucket = car.speed_bucket
        surface = car.surface
        turbo   = car.turbo_active

        # Only re-send when something meaningful changed
        same = (bucket == self._last_speed_bucket and
                surface == self._last_surface and
                turbo == self._last_turbo)
        if same:
            return
        self._last_speed_bucket = bucket
        self._last_surface      = surface
        self._last_turbo        = turbo

        try:
            # R2 — throttle
            if surface == Surface.OIL:
                self.ds.set_trigger_effect("right", TriggerEffect.off())
            elif turbo:
                self.ds.set_trigger_effect(
                    "right", TriggerEffect.vibration(position=0, amplitude=80, frequency=28))
            else:
                end_force = int(10 + car.speed_frac * 200)
                self.ds.set_trigger_effect(
                    "right",
                    TriggerEffect.slope(start=0, end=255,
                                        start_force=10, end_force=end_force))

            # L2 — brake
            if surface == Surface.OIL:
                self.ds.set_trigger_effect("left", TriggerEffect.off())
            elif car.is_braking_hard:
                self.ds.set_trigger_effect("left", TriggerEffect.rigid())
            else:
                self.ds.set_trigger_effect(
                    "left", TriggerEffect.feedback(start=25, force=140))
        except Exception:
            pass

    def _update_led(self, car: Car, dt: float) -> None:
        try:
            if self._winner:
                # Rainbow cycle
                self._rainbow_phase = (self._rainbow_phase + dt * 2.0) % 1.0
                color = _hsv_to_rgb(self._rainbow_phase, 1.0, 1.0)
                self.ds.set_led(*color)
                return

            if self._led_flash_timer > 0:
                self._led_flash_timer -= dt
                if self._led_flash_color:
                    self.ds.set_led(*self._led_flash_color)
                return

            # Speed-based gradient
            color = speed_to_led_color(car.speed_frac, self._base_color)
            self.ds.set_led(*color)
        except Exception:
            pass

    def _update_mic_led(self, car: Car) -> None:
        try:
            if car.turbo_active:
                self.ds.set_mic_led(MicLED.OFF)
            elif car.turbo_cooldown > 0:
                self.ds.set_mic_led(MicLED.BLINK)
            else:
                self.ds.set_mic_led(MicLED.ON)
        except Exception:
            pass

    def flash_led(self, color: Tuple[int,int,int], duration: float = 0.2) -> None:
        self._led_flash_color = color
        self._led_flash_timer = duration

    def trigger_haptic(self, event_name: str) -> None:
        self.haptics.push(event_name)

    def set_winner(self) -> None:
        self._winner = True
        self.trigger_haptic("finish")

    def stop_all(self) -> None:
        try:
            self.ds.set_rumble(0, 0)
            self.ds.set_trigger_off("both")
            self.ds.set_mic_led(MicLED.OFF)
        except Exception:
            pass


# ── Keyboard fallback ─────────────────────────────────────────────────────────

import pygame as _pygame   # imported here to keep top of file clean

class KeyboardPlayer:
    """Keyboard fallback for one player (no haptics)."""

    _KEY_MAPS = [
        # P1: WASD + Left Shift for turbo
        dict(up=_pygame.K_w, down=_pygame.K_s, left=_pygame.K_a,
             right=_pygame.K_d, turbo=_pygame.K_LSHIFT),
        # P2: Arrow keys + Right Shift
        dict(up=_pygame.K_UP, down=_pygame.K_DOWN, left=_pygame.K_LEFT,
             right=_pygame.K_RIGHT, turbo=_pygame.K_RSHIFT),
    ]

    def __init__(self, player_idx: int):
        self.player_idx = player_idx
        self.keys_map   = self._KEY_MAPS[player_idx]
        self._turbo_prev = False

    def read_input(self) -> CarInput:
        keys = _pygame.key.get_pressed()
        m    = self.keys_map
        turbo_now = bool(keys[m["turbo"]])
        turbo_edge = turbo_now and not self._turbo_prev
        self._turbo_prev = turbo_now
        return CarInput(
            throttle=1.0 if keys[m["up"]]    else 0.0,
            brake   =1.0 if keys[m["down"]]  else 0.0,
            steer   =(-1.0 if keys[m["left"]] else
                       1.0 if keys[m["right"]] else 0.0),
            turbo   =turbo_edge,
        )

    def is_options_pressed(self) -> bool:
        keys = _pygame.key.get_pressed()
        return bool(keys[_pygame.K_ESCAPE])

    def is_cross_pressed(self) -> bool:
        keys = _pygame.key.get_pressed()
        # P1 = Enter, P2 = Numpad Enter
        k = _pygame.K_RETURN if self.player_idx == 0 else _pygame.K_KP_ENTER
        return bool(keys[k])

    def update_output(self, car, dt) -> None:
        pass   # no haptics for keyboard

    def flash_led(self, *a, **kw) -> None:
        pass

    def trigger_haptic(self, *a, **kw) -> None:
        pass

    def set_winner(self) -> None:
        pass

    def stop_all(self) -> None:
        pass


# ── Bridge factory ────────────────────────────────────────────────────────────

def create_players(n_controllers: int = 2):
    """
    Try to connect up to n_controllers DualSense controllers.
    Falls back to KeyboardPlayer for any missing slot.
    Returns list of 2 player objects (ControllerPlayer or KeyboardPlayer).
    """
    players = []
    controllers_found = 0

    if HAVE_CONTROLLERS:
        for i in range(n_controllers):
            try:
                ds = DualSense()
                ds.connect()
                ds.listen_async(lambda s: None)   # keep background read going
                players.append(ControllerPlayer(ds, i))
                controllers_found += 1
            except Exception:
                players.append(KeyboardPlayer(i))
    else:
        for i in range(n_controllers):
            players.append(KeyboardPlayer(i))

    # Pad to 2 players
    while len(players) < 2:
        players.append(KeyboardPlayer(len(players)))

    return players, controllers_found


# ── HSV helper ────────────────────────────────────────────────────────────────

def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

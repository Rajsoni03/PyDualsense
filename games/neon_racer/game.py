"""
Neon Racer — GameStateMachine.

States:  MENU → CONNECTING → COUNTDOWN → RACING → PAUSED → RESULTS
"""

import time
from typing import List, Optional

import pygame

from constants import (
    GameState, TOTAL_LAPS, PLAYER_COLORS, WHITE,
    WINDOW_W, WINDOW_H, Surface,
)
from car import Car, CarInput
from track import Track
from renderer import Renderer
from effects import ParticleSystem
from controller_bridge import create_players


_COUNTDOWN_BEATS = [3, 2, 1, 0]   # 0 = "GO!"
_BEAT_INTERVAL   = 1.0             # seconds per beat


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen   = screen
        self.renderer = Renderer(screen)
        self.track    = Track()
        self.state    = GameState.MENU

        self.cars: List[Car]              = []
        self.particles: List[ParticleSystem] = []
        self.players                      = []
        self.n_controllers                = 0

        self._elapsed      = 0.0          # race timer (seconds)
        self._countdown    = 3            # current beat
        self._next_beat    = 0.0          # absolute time for next beat
        self._paused_by    = -1           # player index who paused

        self._winner: Optional[int] = None
        self._ready_flags = [False, False]

        self._font = pygame.font.SysFont("consolas", 28, bold=True)
        self._clock_ref = time.monotonic()

        # Try to detect controllers immediately
        self.players, self.n_controllers = create_players(2)

    # ── Main loop entry ───────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.EventType) -> bool:
        """Returns False to quit."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F4:
                return False
        return True

    def update(self, dt: float) -> bool:
        """Returns False to quit."""
        if self.state == GameState.MENU:
            return self._update_menu(dt)
        elif self.state == GameState.COUNTDOWN:
            return self._update_countdown(dt)
        elif self.state == GameState.RACING:
            return self._update_racing(dt)
        elif self.state == GameState.PAUSED:
            return self._update_paused(dt)
        elif self.state == GameState.RESULTS:
            return self._update_results(dt)
        return True

    def draw(self) -> None:
        if self.state == GameState.MENU:
            self.renderer.draw_menu(self.screen,
                                    self._ready_flags[0],
                                    self._ready_flags[1],
                                    self.n_controllers)
        elif self.state in (GameState.COUNTDOWN, GameState.RACING):
            self.renderer.draw_race(self.track, self.cars,
                                    self.particles, self._elapsed)
            if self.state == GameState.COUNTDOWN:
                self.renderer.draw_countdown(self.screen, self._countdown)
        elif self.state == GameState.PAUSED:
            self.renderer.draw_race(self.track, self.cars,
                                    self.particles, self._elapsed)
            self.renderer.draw_paused(self.screen)
        elif self.state == GameState.RESULTS:
            self.renderer.draw_results(self.screen,
                                       self._winner or 0,
                                       self.cars)

    # ── State: MENU ───────────────────────────────────────────────────────────

    def _update_menu(self, dt: float) -> bool:
        for i, player in enumerate(self.players):
            if player.is_cross_pressed():
                self._ready_flags[i] = True
            if player.is_options_pressed():
                return False   # quit from menu

        # Both ready → start
        if all(self._ready_flags):
            self._start_race()
        return True

    # ── Race setup ────────────────────────────────────────────────────────────

    def _start_race(self) -> None:
        self.cars      = []
        self.particles = []
        for i, (x, y, heading) in enumerate(self.track.start_positions):
            car = Car(x, y, heading, i)
            car.lap_start = 0.0
            self.cars.append(car)
            self.particles.append(ParticleSystem())

        self._elapsed   = 0.0
        self._countdown = 3
        self._next_beat = time.monotonic() + 0.2   # small delay before first beat
        self._winner    = None
        self._paused_by = -1

        # Set controller LEDs to player colours
        for i, player in enumerate(self.players):
            try:
                player.flash_led(PLAYER_COLORS[i], 0.3)
            except Exception:
                pass

        self.state = GameState.COUNTDOWN

    # ── State: COUNTDOWN ─────────────────────────────────────────────────────

    def _update_countdown(self, dt: float) -> bool:
        now = time.monotonic()
        if now >= self._next_beat:
            if self._countdown > 0:
                # Rumble beat
                for player in self.players:
                    player.trigger_haptic("countdown")
                self._countdown -= 1
                self._next_beat  = now + _BEAT_INTERVAL
            else:
                # GO!
                for player in self.players:
                    player.trigger_haptic("go")
                self._clock_ref = time.monotonic()
                self.state = GameState.RACING
        return True

    # ── State: RACING ─────────────────────────────────────────────────────────

    def _update_racing(self, dt: float) -> bool:
        self._elapsed = time.monotonic() - self._clock_ref
        self.track.update(dt)

        for i, (car, player, psys) in enumerate(
                zip(self.cars, self.players, self.particles)):

            if car.finished:
                continue

            # Read input
            inp = player.read_input()
            car.set_input_cache(inp)

            prev_pos = car.position

            # Update car physics
            car.update(inp, dt)

            # Surface detection
            surface = self.track.surface_at(car.x, car.y)
            car.set_surface(surface)

            # Wall collision
            result = self.track.nearest_boundary_push(car.x, car.y, 12)
            if result is not None:
                dx, dy, normal_angle = result
                car.push_back(dx, dy)
                # Only bounce + fire haptics on the first frame of contact
                # (hit_flash > 0 means we're still in the same collision)
                if car.hit_flash <= 0:
                    car.wall_bounce(normal_angle)
                    player.trigger_haptic("wall")
                    player.flash_led((255, 120, 80), 0.15)

            # Boost pad one-shot haptic
            if surface == Surface.BOOST and car._last_surface != Surface.BOOST:
                player.trigger_haptic("boost")
                player.flash_led((255, 255, 255), 0.2)
                car.speed = min(car.speed * 1.15, 320.0)

            # Checkpoint / lap detection
            curr_pos = car.position
            for cp_id in self.track.check_checkpoints(prev_pos, curr_pos):
                car.pass_checkpoint(cp_id)

            if self.track.check_start_finish(prev_pos, curr_pos):
                valid = car.complete_lap(
                    self.track.n_checkpoints, self._elapsed)
                if valid:
                    player.trigger_haptic("lap")
                    player.flash_led(PLAYER_COLORS[i], 0.4)

                    if car.lap >= TOTAL_LAPS:
                        car.finished = True
                        self._winner = i
                        player.set_winner()
                        self.state = GameState.RESULTS
                        # Stop other car from winning
                        for j, oc in enumerate(self.cars):
                            if j != i:
                                oc.finished = True

            # Store surface for next frame boost detection
            car._last_surface = surface

            # Particle trail
            psys.emit_trail(car.x, car.y, car.heading,
                            car.speed, car.color, car.turbo_active)
            psys.update(dt)

            # Controller output (triggers, LED, rumble)
            player.update_output(car, dt)

        # Pause check
        for i, player in enumerate(self.players):
            if player.is_options_pressed():
                self._paused_by = i
                self.state = GameState.PAUSED
                break

        return True

    # ── State: PAUSED ─────────────────────────────────────────────────────────

    def _update_paused(self, dt: float) -> bool:
        p = self.players[self._paused_by] if self._paused_by >= 0 else self.players[0]
        if p.is_options_pressed():
            self._clock_ref = time.monotonic() - self._elapsed
            self.state = GameState.RACING
        elif p.is_cross_pressed():
            return False   # quit
        return True

    # ── State: RESULTS ────────────────────────────────────────────────────────

    def _update_results(self, dt: float) -> bool:
        for i, player in enumerate(self.players):
            if player.is_cross_pressed():
                self._ready_flags = [False, False]
                self.state = GameState.MENU
                # Clean up controllers
                for pl in self.players:
                    pl.stop_all()
                return True
            if player.is_options_pressed():
                return False
        return True

    def shutdown(self) -> None:
        for player in self.players:
            try:
                player.stop_all()
            except Exception:
                pass

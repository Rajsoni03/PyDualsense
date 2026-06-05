"""
Neon Racer — Split-screen renderer.

Layout:
  Left  640 px  → Player 1 viewport
  Right 640 px  → Player 2 viewport
  2 px centre divider

Each viewport has its own camera that follows its car (forward-up orientation).
"""

import math
from typing import List, Tuple, Optional

import pygame
import pygame.font   # explicit — avoids partial-init issue on Python 3.14

from constants import (
    WINDOW_W, WINDOW_H, HALF_W, DIVIDER_W, DIVIDER_COLOR,
    DARK_BG, TRACK_FILL, TRACK_BORDER, TRACK_CENTER,
    GRAVEL_COLOR, BOOST_COLOR, OIL_COLOR,
    HUD_BG, HUD_TEXT, HUD_SPEED_FILL, HUD_TURBO_FILL,
    HUD_AHEAD, HUD_BEHIND, PLAYER_COLORS, WHITE, BLACK,
    Surface, TOTAL_LAPS,
)
from effects import (
    draw_glow_polygon, draw_glow_line, draw_glow_circle,
    world_to_screen, world_poly_to_screen,
)
from car import Car
from track import Track


VIEWPORT_W = HALF_W - DIVIDER_W // 2
VIEWPORT_H = WINDOW_H
CAMERA_SCALE = 0.28   # world units per pixel


_SURFACE_COLORS = {
    Surface.GRAVEL: GRAVEL_COLOR,
    Surface.BOOST:  BOOST_COLOR,
    Surface.OIL:    OIL_COLOR,
}

_CAR_W = 20   # world units
_CAR_H = 12


class Camera:
    """Smooth-following camera for one viewport."""

    def __init__(self):
        self.x     = 0.0
        self.y     = 0.0
        self.angle = 0.0   # degrees (car heading → camera rotates world so car faces up)
        self.scale = CAMERA_SCALE

        self._target_x = 0.0
        self._target_y = 0.0
        self._target_a = 0.0
        _LAG = 0.12   # fraction to close per second (lerp)
        self._lag = _LAG

    def track_car(self, car: Car, dt: float) -> None:
        self._target_x = car.x
        self._target_y = car.y
        self._target_a = car.heading

        t = min(1.0, dt / self._lag)
        self.x     += (self._target_x - self.x) * t
        self.y     += (self._target_y - self.y) * t

        # Smooth angle wrap
        da = (self._target_a - self.angle + 540) % 360 - 180
        self.angle += da * t

    def to_screen(self, wx: float, wy: float,
                  cx: int, cy: int) -> Tuple[int, int]:
        return world_to_screen(wx, wy, self.x, self.y,
                               self.scale, self.angle, cx, cy)

    def poly_to_screen(self, poly, cx: int, cy: int):
        return world_poly_to_screen(poly, self.x, self.y,
                                    self.scale, self.angle, cx, cy)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen  = screen
        self.cameras = [Camera(), Camera()]

        # Viewports as sub-surfaces
        self._vp: List[pygame.Surface] = [
            screen.subsurface(pygame.Rect(0,
                                          0, VIEWPORT_W, VIEWPORT_H)),
            screen.subsurface(pygame.Rect(HALF_W,
                                          0, VIEWPORT_W, VIEWPORT_H)),
        ]

        pygame.font.init()
        self._font_large     = pygame.font.SysFont("consolas", 32, bold=True)
        self._font_med       = pygame.font.SysFont("consolas", 22, bold=True)
        self._font_small     = pygame.font.SysFont("consolas", 16)
        self._font_countdown = pygame.font.SysFont("consolas", 120, bold=True)

    # ── Main draw ─────────────────────────────────────────────────────────────

    def draw_race(self, track: Track, cars: List[Car],
                  particles_list, elapsed: float) -> None:
        self.screen.fill(DARK_BG)

        for i, (vp, cam) in enumerate(zip(self._vp, self.cameras)):
            cam.track_car(cars[i], 1 / 60)
            vp.fill(DARK_BG)
            cx, cy = VIEWPORT_W // 2, VIEWPORT_H // 2

            self._draw_track(vp, cam, track, cx, cy, elapsed)
            for j, car in enumerate(cars):
                particles_list[j].draw(vp, cam.x, cam.y,
                                       cam.scale, cam.angle)
            for car in cars:
                self._draw_car(vp, cam, car, cx, cy)
            self._draw_hud(vp, cars[i], cars[1 - i], elapsed, i)

        # Centre divider
        pygame.draw.rect(self.screen, DIVIDER_COLOR,
                         (HALF_W - 1, 0, DIVIDER_W, WINDOW_H))

    def draw_countdown(self, screen: pygame.Surface, count: int) -> None:
        """Overlay countdown number (3, 2, 1) or 'GO!'."""
        label = str(count) if count > 0 else "GO!"
        color = (255, 80, 80) if count > 0 else (80, 255, 120)
        text  = self._font_countdown.render(label, True, color)
        rect  = text.get_rect(center=(WINDOW_W // 2, WINDOW_H // 2))
        screen.blit(text, rect)

    def draw_menu(self, screen: pygame.Surface,
                  p1_ready: bool, p2_ready: bool,
                  controllers: int) -> None:
        screen.fill(DARK_BG)
        title = self._font_large.render("NEON  RACER", True, PLAYER_COLORS[0])
        screen.blit(title, title.get_rect(center=(WINDOW_W // 2, 220)))

        sub = self._font_med.render("Split-Screen · 3 Laps", True, (150, 150, 200))
        screen.blit(sub, sub.get_rect(center=(WINDOW_W // 2, 270)))

        for i, (ready, color) in enumerate(zip([p1_ready, p2_ready], PLAYER_COLORS)):
            cx = WINDOW_W // 4 + i * WINDOW_W // 2
            label = f"P{i+1}"
            if i < controllers:
                status = "READY" if ready else "Press  X  to  Ready"
            else:
                status = "Connect  Controller"
                color  = (80, 80, 100)
            t1 = self._font_large.render(label,  True, color)
            t2 = self._font_med.render(status, True, color)
            screen.blit(t1, t1.get_rect(center=(cx, 380)))
            screen.blit(t2, t2.get_rect(center=(cx, 430)))

        hint = self._font_small.render(
            "Keyboard fallback: P1=WASD  P2=Arrows  Shift=Turbo", True, (80, 80, 120))
        screen.blit(hint, hint.get_rect(center=(WINDOW_W // 2, 600)))

    def draw_results(self, screen: pygame.Surface,
                     winner: int, cars: List[Car]) -> None:
        screen.fill(DARK_BG)
        w_color = PLAYER_COLORS[winner]
        t = self._font_large.render(f"PLAYER  {winner + 1}  WINS!", True, w_color)
        screen.blit(t, t.get_rect(center=(WINDOW_W // 2, 200)))

        for i, car in enumerate(cars):
            cx = WINDOW_W // 4 + i * WINDOW_W // 2
            c  = PLAYER_COLORS[i]
            lbl = self._font_med.render(f"P{i+1}", True, c)
            screen.blit(lbl, lbl.get_rect(center=(cx, 320)))
            for j, t_lap in enumerate(car.lap_times):
                s = self._font_small.render(
                    f"Lap {j+1}: {t_lap:.2f}s", True, (180, 180, 220))
                screen.blit(s, s.get_rect(center=(cx, 360 + j * 28)))
            best = min(car.lap_times) if car.lap_times else 0
            bs = self._font_small.render(
                f"Best:  {best:.2f}s", True, (255, 220, 80))
            screen.blit(bs, bs.get_rect(center=(cx, 360 + TOTAL_LAPS * 28 + 10)))

        hint = self._font_med.render(
            "X = Rematch      Options = Quit", True, (100, 100, 160))
        screen.blit(hint, hint.get_rect(center=(WINDOW_W // 2, 560)))

    def draw_paused(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))
        t = self._font_large.render("PAUSED", True, WHITE)
        screen.blit(t, t.get_rect(center=(WINDOW_W // 2, WINDOW_H // 2 - 30)))
        h = self._font_med.render("Options = Resume      X = Quit", True, (160, 160, 200))
        screen.blit(h, h.get_rect(center=(WINDOW_W // 2, WINDOW_H // 2 + 30)))

    def update_cameras(self, cars: List[Car], dt: float) -> None:
        for cam, car in zip(self.cameras, cars):
            cam.track_car(car, dt)

    # ── Track drawing ─────────────────────────────────────────────────────────

    def _draw_track(self, vp: pygame.Surface, cam: Camera,
                    track: Track, cx: int, cy: int,
                    elapsed: float) -> None:
        # --- Filled road surface
        outer_s = cam.poly_to_screen(track.outer, cx, cy)
        inner_s = cam.poly_to_screen(track.inner, cx, cy)
        if len(outer_s) > 2:
            pygame.draw.polygon(vp, TRACK_FILL, outer_s)
        if len(inner_s) > 2:
            pygame.draw.polygon(vp, DARK_BG, inner_s)

        # --- Surface zones
        for surface, poly in track.zone_polys:
            color = _SURFACE_COLORS.get(surface)
            if color is None:
                continue
            pts = cam.poly_to_screen(poly, cx, cy)
            if len(pts) < 3:
                continue
            if surface == Surface.BOOST:
                self._draw_boost_zone(vp, pts, color, track.boost_phase)
            else:
                # Dim fill without SRCALPHA surface — blend multiplier approach
                a_frac = (100 if surface == Surface.OIL else 130) / 255
                dim = (int(color[0] * a_frac), int(color[1] * a_frac),
                       int(color[2] * a_frac))
                pygame.draw.polygon(vp, dim, pts)

        # --- Outer boundary glow
        if len(outer_s) > 2:
            draw_glow_polygon(vp, TRACK_BORDER, outer_s, width=3, glow_passes=2)
        if len(inner_s) > 2:
            draw_glow_polygon(vp, TRACK_BORDER, inner_s, width=3, glow_passes=2)

        # --- Dashed centre line
        pts_c = [cam.to_screen(x, y, cx, cy) for x, y in track.centre_line]
        step  = 6
        for i in range(0, len(pts_c) - step, step * 2):
            pygame.draw.line(vp, TRACK_CENTER, pts_c[i], pts_c[i + step - 1], 1)

        # --- Start/finish line
        sf_a, sf_b = track.start_finish
        sa = cam.to_screen(*sf_a, cx, cy)
        sb = cam.to_screen(*sf_b, cx, cy)
        draw_glow_line(vp, WHITE, sa, sb, 3, glow_width=3)

        # --- Checkpoints (faint)
        for a, b in track.checkpoints:
            pas = cam.to_screen(*a, cx, cy)
            pbs = cam.to_screen(*b, cx, cy)
            pygame.draw.line(vp, (40, 40, 80), pas, pbs, 1)

    def _draw_boost_zone(self, vp: pygame.Surface,
                          pts: List[Tuple[int, int]],
                          color: Tuple[int, int, int],
                          phase: float) -> None:
        """Animated scan-line strips for boost pads."""
        dim = (color[0] // 4, color[1] // 4, color[2] // 4)
        pygame.draw.polygon(vp, dim, pts)
        # Bright core border
        draw_glow_polygon(vp, color, pts, width=2, glow_passes=2)
        # Animated arrows
        if len(pts) >= 4:
            cx_p = sum(p[0] for p in pts) // len(pts)
            cy_p = sum(p[1] for p in pts) // len(pts)
            offset = int(phase * 20) - 10
            for ox in [-8, 0, 8]:
                tip = (cx_p + ox, cy_p - 6 + offset)
                bl  = (cx_p + ox - 5, cy_p + 4 + offset)
                br  = (cx_p + ox + 5, cy_p + 4 + offset)
                pygame.draw.polygon(vp, color, [tip, bl, br])

    # ── Car drawing ───────────────────────────────────────────────────────────

    def _draw_car(self, vp: pygame.Surface, cam: Camera,
                  car: Car, cx: int, cy: int) -> None:
        color = car.color

        # Flash white on wall hit
        if car.hit_flash > 0:
            frac  = car.hit_flash / 0.15
            color = _lerp_color(car.color, (255, 255, 255), frac)

        # Build car rectangle corners in world space
        rad = math.radians(car.heading)
        fw  = math.cos(rad)
        fh  = math.sin(rad)
        rw  = -fh
        rh  =  fw

        hw = _CAR_W / 2
        hh = _CAR_H / 2
        corners_world = [
            (car.x + fw * hw + rw * hh,  car.y + fh * hw + rh * hh),
            (car.x + fw * hw - rw * hh,  car.y + fh * hw - rh * hh),
            (car.x - fw * hw - rw * hh,  car.y - fh * hw - rh * hh),
            (car.x - fw * hw + rw * hh,  car.y - fh * hw + rh * hh),
        ]
        corners_screen = [cam.to_screen(wx, wy, cx, cy)
                          for wx, wy in corners_world]

        # Glow halo — dim expanded polygon, no Surface allocation
        gcx = sum(p[0] for p in corners_screen) // 4
        gcy = sum(p[1] for p in corners_screen) // 4
        glow_corners = [
            (int(gcx + (p[0] - gcx) * 1.7), int(gcy + (p[1] - gcy) * 1.7))
            for p in corners_screen
        ]
        glow_color = (color[0] // 4, color[1] // 4, color[2] // 4)
        if len(glow_corners) >= 3:
            pygame.draw.polygon(vp, glow_color, glow_corners)

        # Car body
        if len(corners_screen) >= 3:
            pygame.draw.polygon(vp, color, corners_screen)

        # Player number label
        lbl = self._font_small.render(f"P{car.player_index + 1}", True, WHITE)
        sx, sy = cam.to_screen(car.x, car.y, cx, cy)
        vp.blit(lbl, lbl.get_rect(center=(sx, sy)))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self, vp: pygame.Surface, my_car: Car, other_car: Car,
                  elapsed: float, player_idx: int) -> None:
        W, H = VIEWPORT_W, VIEWPORT_H
        color = PLAYER_COLORS[player_idx]

        # ── Lap counter (top left) ────────────────────────────────────────────
        laps_done = min(my_car.lap, TOTAL_LAPS)
        lap_txt = self._font_med.render(
            f"LAP  {laps_done}/{TOTAL_LAPS}", True, color)
        vp.blit(lap_txt, (12, 12))

        # ── Delta time (top right) ────────────────────────────────────────────
        # Approximate position delta by lap + elapsed as proxy
        my_progress   = my_car.lap + (elapsed - my_car.lap_start) / max(1, elapsed / max(1, my_car.lap or 1))
        opp_progress  = other_car.lap + (elapsed - other_car.lap_start) / max(1, elapsed / max(1, other_car.lap or 1))
        delta         = my_progress - opp_progress
        delta_str     = f"Δ {abs(delta):.1f}s {'↑' if delta >= 0 else '↓'}"
        d_color       = HUD_AHEAD if delta >= 0 else HUD_BEHIND
        delta_txt     = self._font_small.render(delta_str, True, d_color)
        vp.blit(delta_txt, (W - delta_txt.get_width() - 12, 12))

        # ── Speed gauge (bottom, arc-style) ──────────────────────────────────
        speed_int  = int(abs(my_car.speed))
        spd_txt    = self._font_large.render(f"{speed_int:3d}", True, HUD_SPEED_FILL)
        kmh_txt    = self._font_small.render("u/s", True, (100, 100, 160))
        vp.blit(spd_txt, (12, H - 60))
        vp.blit(kmh_txt, (12, H - 24))

        # Speed arc
        _draw_arc_gauge(vp, (90, H - 60), 48, 200, 340,
                        my_car.speed_frac, HUD_SPEED_FILL, color)

        # ── Turbo bar (bottom right) ──────────────────────────────────────────
        bar_w  = 120
        bar_h  = 14
        bx     = W - bar_w - 12
        by     = H - 40
        pygame.draw.rect(vp, (30, 30, 60), (bx, by, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * my_car.turbo_frac)
        if fill_w > 0:
            t_color = HUD_TURBO_FILL if my_car.turbo_ready else (100, 80, 20)
            if my_car.turbo_active:
                t_color = (255, 180, 0)
            pygame.draw.rect(vp, t_color,
                             (bx, by, fill_w, bar_h), border_radius=3)
        turbo_lbl = self._font_small.render("TURBO", True,
                                            HUD_TURBO_FILL if my_car.turbo_ready else (80, 70, 30))
        vp.blit(turbo_lbl, (bx, by - 18))

        # ── Position indicator ────────────────────────────────────────────────
        pos_str = "LEAD" if my_car.lap >= other_car.lap else "P2"
        if my_car.lap > other_car.lap:
            pos_str = "P1  LEAD"
        elif my_car.lap < other_car.lap:
            pos_str = "P2  BEHIND"
        pos_txt = self._font_small.render(pos_str, True, color)
        vp.blit(pos_txt, pos_txt.get_rect(right=W - 12, y=H - 70))


# ── Arc gauge helper ──────────────────────────────────────────────────────────

def _draw_arc_gauge(surf: pygame.Surface,
                    centre: Tuple[int, int],
                    radius: int,
                    start_deg: float, end_deg: float,
                    frac: float,
                    fill_color: Tuple[int, int, int],
                    border_color: Tuple[int, int, int]) -> None:
    rect = pygame.Rect(centre[0] - radius, centre[1] - radius,
                       radius * 2, radius * 2)
    # Background arc
    try:
        pygame.draw.arc(surf, (40, 40, 80), rect,
                        math.radians(start_deg), math.radians(end_deg), 4)
        if frac > 0.01:
            span = end_deg - start_deg
            pygame.draw.arc(surf, fill_color, rect,
                            math.radians(start_deg),
                            math.radians(start_deg + span * frac), 5)
        pygame.draw.arc(surf, border_color, rect,
                        math.radians(start_deg), math.radians(end_deg), 2)
    except Exception:
        pass   # arc can throw on degenerate rects


# ── Colour helpers ────────────────────────────────────────────────────────────

def _lerp_color(a: Tuple[int, int, int],
                b: Tuple[int, int, int],
                t: float) -> Tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def speed_to_led_color(frac: float,
                       base_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """HSV-like gradient: blue(0) → cyan(0.4) → yellow(0.7) → red(1.0)."""
    if frac < 0.4:
        t = frac / 0.4
        return _lerp_color((0, 80, 255), (0, 220, 255), t)
    elif frac < 0.7:
        t = (frac - 0.4) / 0.3
        return _lerp_color((0, 220, 255), (255, 220, 0), t)
    else:
        t = (frac - 0.7) / 0.3
        return _lerp_color((255, 220, 0), (255, 30, 30), t)

"""
Neon Racer — Particle trail system and neon glow helpers.
"""

import math
import random
from typing import List, Tuple

import pygame

from constants import (
    PARTICLE_LIFE, PARTICLE_COUNT, BOOST_PARTICLE_COUNT,
    GLOW_RADIUS, GLOW_ALPHA,
)


# ── Particle ──────────────────────────────────────────────────────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 color: Tuple[int, int, int], size: float):
        self.x        = x
        self.y        = y
        self.vx       = vx
        self.vy       = vy
        self.life     = PARTICLE_LIFE
        self.max_life = PARTICLE_LIFE
        self.color    = color
        self.size     = size

    def update(self, dt: float) -> None:
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    @property
    def alpha(self) -> int:
        return int(255 * max(0.0, self.life / self.max_life))

    @property
    def radius(self) -> float:
        frac = self.life / self.max_life
        return max(1.0, self.size * frac)


# ── Particle System ───────────────────────────────────────────────────────────

class ParticleSystem:
    def __init__(self):
        self._particles: List[Particle] = []

    def emit_trail(self, x: float, y: float, heading: float,
                   speed: float, color: Tuple[int, int, int],
                   turbo: bool = False) -> None:
        """Emit trail particles behind the car."""
        if speed < 10:
            return

        count = BOOST_PARTICLE_COUNT if turbo else PARTICLE_COUNT
        speed_frac = min(1.0, speed / 320.0)

        # Back of car — opposite to heading
        rad   = math.radians(heading + 180)
        bx    = x + math.cos(rad) * 12
        by    = y + math.sin(rad) * 12

        for _ in range(count):
            spread = math.radians(random.uniform(-30, 30))
            angle  = rad + spread
            v_mag  = random.uniform(20, 60 + speed_frac * 80)
            vx     = math.cos(angle) * v_mag
            vy     = math.sin(angle) * v_mag

            if turbo:
                r = min(255, color[0] + 80)
                g = min(255, color[1] + 80)
                b = min(255, color[2] + 80)
                p_color = (r, g, b)
                size = random.uniform(5, 9)
            else:
                size  = random.uniform(2, 4 + speed_frac * 3)
                p_color = color

            self._particles.append(
                Particle(bx + random.uniform(-4, 4),
                         by + random.uniform(-4, 4),
                         vx, vy, p_color, size)
            )

    def update(self, dt: float) -> None:
        for p in self._particles:
            p.update(dt)
        self._particles = [p for p in self._particles if p.alive]

    def draw(self, surface: pygame.Surface,
             cam_x: float, cam_y: float, cam_scale: float,
             cam_angle: float) -> None:
        """Draw particles transformed into camera space."""
        for p in self._particles:
            sx, sy = world_to_screen(p.x, p.y, cam_x, cam_y,
                                     cam_scale, cam_angle,
                                     surface.get_width() // 2,
                                     surface.get_height() // 2)
            r = max(1, int(p.radius * cam_scale))
            alpha = p.alpha
            if r < 1 or alpha < 5:
                continue
            draw_glow_circle(surface, p.color, (sx, sy), r, alpha)


# ── Glow drawing helpers ──────────────────────────────────────────────────────

def draw_glow_circle(surf: pygame.Surface,
                     color: Tuple[int, int, int],
                     pos: Tuple[int, int],
                     radius: int,
                     alpha: int = 200) -> None:
    """Draw a circle with a soft glow halo — no Surface allocation."""
    # Outer glow: dim larger circle (avoids SRCALPHA surface per call)
    t = alpha / 765  # 255*3
    glow_color = (int(color[0] * t), int(color[1] * t), int(color[2] * t))
    if radius > 1:
        pygame.draw.circle(surf, glow_color, pos, radius * 2)
    # Core bright circle
    pygame.draw.circle(surf, color, pos, max(1, radius))


def draw_glow_line(surf: pygame.Surface,
                   color: Tuple[int, int, int],
                   start: Tuple[int, int],
                   end: Tuple[int, int],
                   width: int,
                   glow_width: int = 0) -> None:
    """Draw a line with an optional soft glow behind it."""
    if glow_width > 0:
        glow_color = (
            min(255, color[0] // 2),
            min(255, color[1] // 2),
            min(255, color[2] // 2),
        )
        pygame.draw.line(surf, glow_color, start, end, width + glow_width * 2)
    pygame.draw.line(surf, color, start, end, width)


def draw_glow_polygon(surf: pygame.Surface,
                      color: Tuple[int, int, int],
                      points: List[Tuple[int, int]],
                      width: int = 0,
                      glow_passes: int = 2) -> None:
    """Fill or outline a polygon with a neon glow border."""
    if width == 0:
        # Filled
        dim_color = (color[0] // 3, color[1] // 3, color[2] // 3)
        pygame.draw.polygon(surf, dim_color, points)
    # Glow passes
    for i in range(glow_passes, 0, -1):
        g = (color[0] // (i + 1), color[1] // (i + 1), color[2] // (i + 1))
        pygame.draw.polygon(surf, g, points, width + i * 3)
    # Core bright line
    pygame.draw.polygon(surf, color, points, max(1, width))


# ── Camera transform ──────────────────────────────────────────────────────────

def world_to_screen(wx: float, wy: float,
                    cam_x: float, cam_y: float,
                    scale: float, angle_deg: float,
                    screen_cx: int, screen_cy: int) -> Tuple[int, int]:
    """Transform a world point to screen (viewport) coordinates."""
    dx = wx - cam_x
    dy = wy - cam_y
    rad = math.radians(-angle_deg)
    rx  = dx * math.cos(rad) - dy * math.sin(rad)
    ry  = dx * math.sin(rad) + dy * math.cos(rad)
    sx  = int(screen_cx + rx * scale)
    sy  = int(screen_cy + ry * scale)
    return sx, sy


def world_poly_to_screen(poly, cam_x, cam_y, scale, angle_deg,
                         screen_cx, screen_cy):
    return [world_to_screen(x, y, cam_x, cam_y, scale, angle_deg,
                            screen_cx, screen_cy) for x, y in poly]

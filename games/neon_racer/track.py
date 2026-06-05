"""
Neon Racer — Track definition, spline, surface zones, lap detection.

Track is defined as a list of (x, y) centre-line waypoints.
A Catmull-Rom spline is built from them and expanded left/right by TRACK_WIDTH/2
to produce inner/outer boundary polygons.

Surface zones are simple convex polygons overlaid on the track.
"""

import math
from typing import List, Tuple, Optional

from constants import TRACK_WIDTH, TOTAL_LAPS, Surface


# ── Type aliases ──────────────────────────────────────────────────────────────
Point  = Tuple[float, float]
Poly   = List[Point]


# ── Track waypoints (world coordinates) ──────────────────────────────────────
# Designed to fit a 2400 × 1600 world — camera will pan/zoom.

_RAW_WAYPOINTS: List[Point] = [
    (1200, 200),
    (1900, 180),
    (2200, 350),
    (2300, 650),
    (2150, 950),
    (1800, 1050),
    (1400, 1000),
    (1100, 1150),
    ( 900, 1350),
    ( 600, 1400),
    ( 280, 1300),
    ( 150, 1050),
    ( 180,  700),
    ( 320,  480),
    ( 600,  300),
    ( 900,  200),
]

# Surface zone definitions: (Surface, list-of-4-points polygon in world coords)
_ZONE_DEFS: List[Tuple[Surface, Poly]] = [
    # Gravel patch — sweeping right-hander after start
    (Surface.GRAVEL, [
        (2050, 380), (2200, 380), (2230, 600), (2080, 610),
    ]),
    # Boost straight — bottom of the lap
    (Surface.BOOST, [
        (700, 1340), (1050, 1340), (1050, 1410), (700, 1410),
    ]),
    # Boost pad — entry to back straight
    (Surface.BOOST, [
        (300,  650), (450,  650), (450,  760), (300,  760),
    ]),
    # Oil slick — tight left-hander
    (Surface.OIL, [
        (140, 1000), (340, 1000), (340, 1150), (140, 1150),
    ]),
    # Gravel — final chicane
    (Surface.GRAVEL, [
        (700,  220), (900,  220), (900,  340), (700,  340),
    ]),
]

# Checkpoints (perpendicular gate across track at key positions)
# Each checkpoint is defined as two endpoints; index is the checkpoint ID.
_CHECKPOINT_DEFS: List[Tuple[Point, Point]] = [
    ((1500,  900), (1500, 1100)),   # 0 — mid-section
    (( 700, 1350), ( 700, 1450)),   # 1 — bottom straight (also boost)
    (( 150,  900), ( 400,  900)),   # 2 — left loop
    (( 350,  400), ( 600,  450)),   # 3 — returning sector
]

# Start/finish line
START_FINISH: Tuple[Point, Point] = ((1100, 160), (1100, 280))

# Car start positions  [P1, P2] with heading (degrees, 0=right)
START_POSITIONS: List[Tuple[float, float, float]] = [
    (1160, 195, 0),    # P1 — offset slightly left
    (1240, 210, 0),    # P2 — offset slightly right
]


# ── Spline utilities ──────────────────────────────────────────────────────────

def _catmull_rom(p0: Point, p1: Point, p2: Point, p3: Point,
                 t: float) -> Point:
    t2 = t * t
    t3 = t2 * t
    x = 0.5 * ((2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2
                + (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3)
    y = 0.5 * ((2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2
                + (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3)
    return (x, y)


def _build_spline(waypoints: List[Point], steps_per_seg: int = 20) -> List[Point]:
    pts = waypoints
    n   = len(pts)
    result: List[Point] = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            result.append(_catmull_rom(p0, p1, p2, p3, t))
    return result


def _offset_polygon(centre_line: List[Point],
                    half_width: float) -> Tuple[Poly, Poly]:
    """Build inner and outer boundary polygons from a closed centre line."""
    n      = len(centre_line)
    inner: Poly = []
    outer: Poly = []
    for i in range(n):
        p_prev = centre_line[(i - 1) % n]
        p_next = centre_line[(i + 1) % n]
        dx = p_next[0] - p_prev[0]
        dy = p_next[1] - p_prev[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue
        nx = -dy / length
        ny =  dx / length
        cx, cy = centre_line[i]
        inner.append((cx + nx * half_width, cy + ny * half_width))
        outer.append((cx - nx * half_width, cy - ny * half_width))
    return inner, outer


# ── Point-in-polygon ──────────────────────────────────────────────────────────

def _point_in_poly(px: float, py: float, poly: Poly) -> bool:
    n      = len(poly)
    inside = False
    j      = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _segments_intersect(a1: Point, a2: Point,
                        b1: Point, b2: Point) -> bool:
    """Returns True if line segment a1–a2 crossed line segment b1–b2."""
    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = _cross(b1, b2, a1)
    d2 = _cross(b1, b2, a2)
    d3 = _cross(a1, a2, b1)
    d4 = _cross(a1, a2, b2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


# ── Main Track class ──────────────────────────────────────────────────────────

class Track:
    def __init__(self):
        self.waypoints  = _RAW_WAYPOINTS
        self.centre_line: List[Point] = _build_spline(self.waypoints, steps_per_seg=24)
        half = TRACK_WIDTH / 2
        self.inner, self.outer = _offset_polygon(self.centre_line, half)

        self.zone_polys: List[Tuple[Surface, Poly]] = _ZONE_DEFS
        self.checkpoints   = _CHECKPOINT_DEFS
        self.start_finish  = START_FINISH
        self.start_positions = START_POSITIONS
        self.total_laps    = TOTAL_LAPS
        self.n_checkpoints = len(self.checkpoints)

        # Boost pad animation phase (shared across renderer)
        self.boost_phase = 0.0

        # Precompute boundary edges (avoids per-frame list creation)
        self._boundary_edges = (
            list(zip(self.outer, self.outer[1:] + [self.outer[0]])) +
            list(zip(self.inner, self.inner[1:] + [self.inner[0]]))
        )

    def update(self, dt: float) -> None:
        self.boost_phase = (self.boost_phase + dt * 2.0) % 1.0

    # ── Per-car queries ───────────────────────────────────────────────────────

    def surface_at(self, x: float, y: float) -> Surface:
        for surface, poly in self.zone_polys:
            if _point_in_poly(x, y, poly):
                return surface
        return Surface.ROAD

    def is_on_track(self, x: float, y: float) -> bool:
        """True if point is between inner and outer boundaries."""
        return _point_in_poly(x, y, self.outer) and \
               not _point_in_poly(x, y, self.inner)

    def nearest_boundary_push(self, x: float, y: float,
                               radius: float) -> Optional[Tuple[float, float, float]]:
        """
        Check if car (circle of `radius`) is off-track.
        Returns (push_dx, push_dy, wall_normal_angle) if colliding, else None.

        Push direction: car → nearest boundary point → past it onto the track.
        This is always correct regardless of polygon winding direction.
        """
        if self.is_on_track(x, y):
            return None

        nearest_dist = float("inf")
        nearest_bx, nearest_by = x, y

        for (ax, ay), (bx, by) in self._boundary_edges:
            closest, _ = _closest_point_on_segment((x, y), (ax, ay), (bx, by))
            dist = math.hypot(closest[0] - x, closest[1] - y)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_bx, nearest_by = closest[0], closest[1]

        # Vector from car toward nearest boundary point
        dx = nearest_bx - x
        dy = nearest_by - y
        dist = math.hypot(dx, dy)

        if dist < 1e-9:
            # Car is exactly on boundary edge — push arbitrarily sideways
            return (radius + 4, 0.0, 90.0)

        # Normalise
        nx = dx / dist
        ny = dy / dist

        # Push car through the boundary by (dist + radius + 4) so it lands
        # radius+4 units past the boundary = back onto the track surface.
        push_amount  = dist + radius + 4
        # Wall normal points back toward the car (used for bounce reflection)
        normal_angle = math.degrees(math.atan2(-ny, -nx))

        return (nx * push_amount, ny * push_amount, normal_angle)

    def check_checkpoints(self, prev: Point, curr: Point) -> List[int]:
        """Return list of checkpoint IDs crossed between prev and curr positions."""
        crossed = []
        for cp_id, (a, b) in enumerate(self.checkpoints):
            if _segments_intersect(prev, curr, a, b):
                crossed.append(cp_id)
        return crossed

    def check_start_finish(self, prev: Point, curr: Point) -> bool:
        a, b = self.start_finish
        return _segments_intersect(prev, curr, a, b)

    # ── Bounding box (for renderer world-bounds) ──────────────────────────────

    @property
    def world_bounds(self) -> Tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) of the outer boundary."""
        xs = [p[0] for p in self.outer]
        ys = [p[1] for p in self.outer]
        return min(xs), min(ys), max(xs), max(ys)


# ── Geometry helper ───────────────────────────────────────────────────────────

def _closest_point_on_segment(p: Point, a: Point,
                               b: Point) -> Tuple[Point, float]:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    len2   = dx * dx + dy * dy
    if len2 < 1e-12:
        return a, 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
    return (ax + t * dx, ay + t * dy), t

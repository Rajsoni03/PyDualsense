"""
Neon Racer — shared constants, tuning values, color palette.
"""

from enum import Enum, auto

# ── Window ────────────────────────────────────────────────────────────────────

WINDOW_W = 1280
WINDOW_H = 720
HALF_W   = WINDOW_W // 2
FPS      = 60

DIVIDER_W = 2          # width of center screen divider in px

# ── Physics ───────────────────────────────────────────────────────────────────

MAX_SPEED        = 320.0   # world units / second at full throttle
ACCELERATION     = 280.0   # world units / s² at full throttle (R2=255)
BRAKE_FORCE      = 420.0   # world units / s² at full brake (L2=255)
FRICTION         = 90.0    # passive deceleration (world units / s²) on road
STEER_RATE       = 160.0   # degrees / second at max stick deflection, at low speed
STEER_SPEED_DIV  = 2.2     # steering narrows as speed increases (divisor)
REVERSE_MAX      = 60.0    # max reversing speed
WHEEL_LOCK_SPEED = 30.0    # below this speed brakes fully stop the car

TURBO_MULTIPLIER = 1.42    # speed multiplier during turbo
TURBO_DURATION   = 3.0     # seconds
TURBO_COOLDOWN   = 8.0     # seconds after turbo ends before next use

WALL_BOUNCE_LOSS = 0.35    # fraction of speed lost on wall hit
GYRO_BLEND       = 0.30    # weight of gyro vs stick steering (default)
GYRO_SCALE       = 0.012   # accel.x raw → steering degrees per frame

DEADZONE         = 0.18    # stick deadzone (normalised 0–1)

# ── Track ─────────────────────────────────────────────────────────────────────

TRACK_WIDTH      = 130     # world units — lane width
TOTAL_LAPS       = 3

# ── Surface types ─────────────────────────────────────────────────────────────

class Surface(Enum):
    ROAD    = auto()
    GRAVEL  = auto()
    BOOST   = auto()
    OIL     = auto()

SURFACE_FRICTION = {
    Surface.ROAD:   1.0,
    Surface.GRAVEL: 2.2,
    Surface.BOOST:  0.6,
    Surface.OIL:    0.08,
}

SURFACE_MAX_SPEED = {
    Surface.ROAD:   1.0,
    Surface.GRAVEL: 0.78,
    Surface.BOOST:  1.18,
    Surface.OIL:    1.0,
}

# ── Neon colour palette ───────────────────────────────────────────────────────

BLACK       = (  0,   0,   0)
WHITE       = (255, 255, 255)
DARK_BG     = (  5,   5,  18)   # near-black dark blue background

# Track colours
TRACK_FILL     = ( 18,  18,  35)
TRACK_BORDER   = ( 80, 180, 255)   # bright blue glow border
TRACK_CENTER   = ( 60,  60,  90)   # faint center divider dashes
GRAVEL_COLOR   = (160,  80,  20)
BOOST_COLOR    = (  0, 230, 230)
OIL_COLOR      = ( 30, 120,  30)

# Player base colours
P1_COLOR       = (  0, 220, 255)   # cyan
P2_COLOR       = (255,  30, 220)   # magenta

PLAYER_COLORS  = [P1_COLOR, P2_COLOR]

# HUD colours
HUD_BG         = ( 10,  10,  25, 160)   # semi-transparent panel
HUD_TEXT       = (220, 220, 255)
HUD_SPEED_FILL = (  0, 200, 255)
HUD_TURBO_FILL = (255, 220,   0)
HUD_AHEAD      = ( 80, 255, 120)   # Δ time when ahead
HUD_BEHIND     = (255,  80,  80)   # Δ time when behind

DIVIDER_COLOR  = (180, 180, 255)

# ── Glow / particle settings ──────────────────────────────────────────────────

GLOW_RADIUS    = 12     # extra px for glow halo on track borders
GLOW_ALPHA     = 60     # alpha of outer glow
PARTICLE_LIFE  = 0.40   # seconds each trail particle lives
PARTICLE_COUNT = 3      # particles emitted per frame when moving
BOOST_PARTICLE_COUNT = 8

# ── Haptic event priorities (higher = wins if two events collide) ─────────────

HAPTIC_PRIORITY = {
    "finish":    100,
    "wall":       80,
    "lap":        70,
    "boost":      60,
    "countdown":  50,
    "gravel":     20,
    "turbo":      15,
    "oil":        10,
}

# ── Rumble presets (right_motor, left_motor, duration_seconds) ────────────────

RUMBLE = {
    "gravel":    ( 50,  70, 0.0),    # 0.0 = continuous while on surface
    "boost":     (210,   0, 0.20),
    "wall":      (200, 190, 0.18),
    "lap":       (160, 100, 0.35),
    "turbo":     ( 90,  40, 0.0),    # continuous while active
    "oil":       (  0,  30, 0.0),
    "countdown": (120, 120, 0.12),
    "go":        (220, 220, 0.25),
    "finish":    (255, 255, 0.50),
}

# ── Game states ───────────────────────────────────────────────────────────────

class GameState(Enum):
    MENU       = auto()
    CONNECTING = auto()
    COUNTDOWN  = auto()
    RACING     = auto()
    RESULTS    = auto()
    PAUSED     = auto()

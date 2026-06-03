#!/usr/bin/env python3
"""
robotics_gamepad.py — Interactive terminal robotics gamepad demo.

Demonstrates adaptive triggers, touchpad visualisation, D-pad mode switching,
IMU telemetry, rumble, and lightbar — all live-rendered in the terminal.

Controls
────────
  Left stick         forward / backward + steer
  R2                 throttle  (feel changes per mode)
  L2                 brake     (weapon-click feel)
  D-Pad ↑↓←→        switch drive mode
  △ Triangle         cycle lightbar colour
  □ Square           rumble burst
  ○ Circle           emergency stop  (RIGID on both triggers)
  ✕ Cross            quit

Drive modes  (D-Pad)
────────────────────
  ↑ NORMAL     R2 = light feedback    L2 = brake click
  ↓ PRECISION  R2 = slope 0→max       L2 = heavy feedback
  ← SPEED      R2 = engine vibration  L2 = brake click
  → CRAWL      R2 = rigid wall        L2 = rigid wall
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState
from pydualsense.protocol.constants import DPadDirection, PlayerLED
from pydualsense.features.triggers import TriggerEffect
from pydualsense.utils.deadzone import apply_deadzone_circular

# ── Constants ─────────────────────────────────────────────────────────────────

DEADZONE   = 0.10
BAR_W      = 22     # signed bar total width (must be even)
BAR_S      = 10     # fill bar width for triggers
TP_COLS    = 27     # touchpad grid columns  (27*2-1 + 1 pad = 54 chars ≤ 58 inner)
TP_ROWS    = 5      # touchpad grid rows

# Box geometry – widths include the two │ borders
W   = 60            # main box total width
IW  = W - 2         # 58 inner chars
LW  = 36            # trigger sub-box width
LI  = LW - 2        # 34 inner
RW  = 22            # dpad sub-box width  (LW + 2 gap + RW == W)
RI  = RW - 2        # 20 inner

DRIVE_MODES = {
    "NORMAL":    {
        "led":  (0, 200, 0),
        "r2":   lambda: TriggerEffect.feedback(start=0,  force=90),
        "l2":   lambda: TriggerEffect.weapon(start=50, end=180, force=200),
        "leds": PlayerLED.player(1),
    },
    "PRECISION": {
        "led":  (0, 100, 255),
        "r2":   lambda: TriggerEffect.slope(start=0, end=255, start_force=30, end_force=220),
        "l2":   lambda: TriggerEffect.feedback(start=0, force=200),
        "leds": PlayerLED.player(2),
    },
    "SPEED":     {
        "led":  (255, 80, 0),
        "r2":   lambda: TriggerEffect.vibration(position=0, amplitude=180, frequency=28),
        "l2":   lambda: TriggerEffect.weapon(start=50, end=180, force=200),
        "leds": PlayerLED.player(3),
    },
    "CRAWL":     {
        "led":  (128, 0, 200),
        "r2":   lambda: TriggerEffect.rigid(),
        "l2":   lambda: TriggerEffect.rigid(),
        "leds": PlayerLED.player(4),
    },
}

DPAD_TO_MODE = {
    DPadDirection.N: "NORMAL",
    DPadDirection.S: "PRECISION",
    DPadDirection.W: "SPEED",
    DPadDirection.E: "CRAWL",
}

LED_COLORS = [(0, 200, 0), (255, 80, 0), (0, 100, 255), (200, 0, 200), (255, 200, 0)]

# ── Mutable state ─────────────────────────────────────────────────────────────

_S = {
    "forward": 0.0, "turn": 0.0, "boost": 0.0,
    "lw": 0.0, "rw": 0.0,
    "l2": 0, "r2": 0,
    "stopped": False,
    "mode": "NORMAL",
    "led_idx": 0,
    "btns": [],
    "dpad": DPadDirection.NEUTRAL,
    "gyro": (0, 0, 0),
    "accel": (0, 0, 0),
    "tp0": None, "tp1": None,   # TouchFinger or None
    "battery": 0, "charging": False,
    "_prev_mode":    None,
    "_prev_stopped": None,
    "_tri": False,
    "_sq":  False,
}

# ── Rendering helpers ─────────────────────────────────────────────────────────

def _signed_bar(val: float) -> str:
    """Centred signed bar, total width = BAR_W+2 chars."""
    half   = BAR_W // 2
    filled = min(int(abs(val) * half), half)
    if val >= 0:
        l = " " * half
        r = "█" * filled + "░" * (half - filled)
    else:
        l = "░" * (half - filled) + "█" * filled
        r = " " * half
    return f"[{l}|{r}]"

def _fill_bar(val: int, width: int = BAR_S) -> str:
    filled = min(int(val / 255 * width), width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def _dpad_glyph(d: DPadDirection) -> list:
    """Return 3 lines of 7 chars each representing the D-pad state."""
    rows = {
        DPadDirection.N:       ["   ▲   ", "   +   ", "       "],
        DPadDirection.NE:      ["   ▲   ", "   + ► ", "       "],
        DPadDirection.E:       ["       ", "   + ► ", "       "],
        DPadDirection.SE:      ["       ", "   + ► ", "   ▼   "],
        DPadDirection.S:       ["       ", "   +   ", "   ▼   "],
        DPadDirection.SW:      ["       ", " ◄ +   ", "   ▼   "],
        DPadDirection.W:       ["       ", " ◄ +   ", "       "],
        DPadDirection.NW:      ["   ▲   ", " ◄ +   ", "       "],
        DPadDirection.NEUTRAL: ["       ", "   +   ", "       "],
    }
    return rows.get(d, ["       ", "   +   ", "       "])

def _touchpad_grid(f0, f1) -> list:
    """TP_ROWS lines; each is exactly IW chars (padded)."""
    grid = [["·"] * TP_COLS for _ in range(TP_ROWS)]
    for f, ch in ((f0, "0"), (f1, "1")):
        if f and f.active:
            col = min(int(f.x / 1920 * TP_COLS), TP_COLS - 1)
            row = min(int(f.y / 1080 * TP_ROWS), TP_ROWS - 1)
            grid[row][col] = ch
    raw_lines = [" " + " ".join(row) for row in grid]   # 1 + 53 = 54 chars
    return [f"{line:<{IW}}" for line in raw_lines]

# Box line helpers
def _bl(content: str) -> str:
    """Main box line: pad to IW and wrap with │."""
    return f"│{content:<{IW}}│"

def _sub(left: str, right: str) -> str:
    """Side-by-side sub-box line."""
    return f"│{left:<{LI}}│  │{right:<{RI}}│"

def _render():
    s        = _S
    bat_icon = "~" if s["charging"] else " "
    bat_str  = f"BAT:{bat_icon}{s['battery']:3d}%"
    status   = "[STOP]" if s["stopped"] else f"[{s['mode']:<9}]"
    btns_str = " ".join(s["btns"]) if s["btns"] else "-"

    dpad = _dpad_glyph(s["dpad"])
    tp   = _touchpad_grid(s["tp0"], s["tp1"])

    gx, gy, gz = s["gyro"]
    ax, ay, az = s["accel"]
    spd = (0.5 + 0.5 * s["boost"]) * 100

    # Pre-build bar strings (fixed widths)
    fwd_bar = _signed_bar(s["forward"])   # 24 chars
    trn_bar = _signed_bar(s["turn"])      # 24 chars
    l2_bar  = _fill_bar(s["l2"])          # 12 chars
    r2_bar  = _fill_bar(s["r2"])          # 12 chars

    out = ["\033[H\033[J"]
    out.append("╔" + "═" * IW + "╗")
    out.append(_bl("    DualSense Robotics Gamepad Demo"))
    out.append("╚" + "═" * IW + "╝")
    out.append(_bl(f"  {bat_str}   {status}   Btns: {btns_str}"))
    out.append(_bl(""))

    out.append("├" + "─" * IW + "┤")
    out.append(_bl(f"  Forward  {fwd_bar}  {s['forward']:+.2f}"))
    out.append(_bl(f"  Turn     {trn_bar}  {s['turn']:+.2f}"))
    out.append(_bl(f"  L:{s['lw']:+.2f}  R:{s['rw']:+.2f}   Speed:{spd:3.0f}%"))
    out.append("├" + "─" * IW + "┤")

    # Triggers + D-pad: LW=36, gap=2, RW=22, total=60
    out.append(f"┌{'─' * LI}┐  ┌{'─' * RI}┐")
    out.append(_sub(f"  Triggers", f"  D-Pad"))
    out.append(_sub(f"  L2 {l2_bar}  {s['l2']:3d}", f"  {dpad[0]}"))
    out.append(_sub(f"  R2 {r2_bar}  {s['r2']:3d}", f"  {dpad[1]}"))
    out.append(_sub(f"  Mode: {s['mode']:<9}", f"  {dpad[2]}"))
    out.append(f"└{'─' * LI}┘  └{'─' * RI}┘")

    out.append("├" + "─" * IW + "┤")
    out.append(_bl("  Touchpad"))
    for line in tp:
        out.append(f"│{line}│")
    out.append("├" + "─" * IW + "┤")

    out.append(_bl("  IMU"))
    out.append(_bl(f"  Gyro   X:{gx:+7d}  Y:{gy:+7d}  Z:{gz:+7d}"))
    out.append(_bl(f"  Accel  X:{ax:+7d}  Y:{ay:+7d}  Z:{az:+7d}"))
    out.append("└" + "─" * IW + "┘")
    out.append("  △=LED  □=rumble  ○=e-stop  ✕=quit  |  D-Pad: ↑NORMAL ↓PRECISION ←SPEED →CRAWL")

    print("\n".join(out), end="", flush=True)


# ── Trigger management ────────────────────────────────────────────────────────

def _apply_triggers(ds: DualSense):
    s        = _S
    mode     = s["mode"]
    stopped  = s["stopped"]
    key      = (mode, stopped)
    if key == s["_prev_mode"]:
        return
    s["_prev_mode"] = key

    if stopped:
        ds.set_trigger_effect("right", TriggerEffect.rigid())
        ds.set_trigger_effect("left",  TriggerEffect.rigid())
    else:
        cfg = DRIVE_MODES[mode]
        ds.set_trigger_effect("right", cfg["r2"]())
        ds.set_trigger_effect("left",  cfg["l2"]())


# ── Input callback ────────────────────────────────────────────────────────────

def on_state(state: InputState, ds: DualSense):
    s = _S

    # Sticks
    nx, ny = state.left_stick.normalised()
    rx, _  = state.right_stick.normalised()
    nx, ny = apply_deadzone_circular(nx, ny, DEADZONE)
    rx, _  = apply_deadzone_circular(rx, 0.0, DEADZONE)

    forward = -ny
    turn    = rx
    boost   = state.r2 / 255.0
    speed   = 0.5 + 0.5 * boost

    # D-Pad mode switch (rising edge on each direction)
    dpad = state.dpad
    if dpad in DPAD_TO_MODE and dpad != s["dpad"]:
        new_mode = DPAD_TO_MODE[dpad]
        if new_mode != s["mode"]:
            s["mode"] = new_mode
            cfg = DRIVE_MODES[new_mode]
            ds.set_led(*cfg["led"])
            ds.set_player_leds(cfg["leds"])
    s["dpad"] = dpad

    # Emergency stop (○)
    stopped = state.buttons.circle
    if stopped:
        ds.set_led(255, 0, 0)

    # Drive
    if stopped:
        lw, rw = 0.0, 0.0
    else:
        lw = forward * speed + turn * speed
        rw = forward * speed - turn * speed

    # Triangle: cycle LED (rising edge)
    if state.buttons.triangle and not s["_tri"]:
        s["led_idx"] = (s["led_idx"] + 1) % len(LED_COLORS)
        ds.set_led(*LED_COLORS[s["led_idx"]])
    s["_tri"] = state.buttons.triangle

    # Square: rumble (rising edge = burst, hold = continuous)
    if state.buttons.square and not s["_sq"]:
        ds.set_rumble(180, 100)
    elif not state.buttons.square and s["_sq"]:
        ds.set_rumble(0, 0)
    s["_sq"] = state.buttons.square

    # Active buttons label
    pressed = []
    if state.buttons.cross:          pressed.append("✕")
    if state.buttons.circle:         pressed.append("○")
    if state.buttons.square:         pressed.append("□")
    if state.buttons.triangle:       pressed.append("△")
    if state.buttons.l1:             pressed.append("L1")
    if state.buttons.r1:             pressed.append("R1")
    if state.buttons.l2:             pressed.append("L2")
    if state.buttons.r2:             pressed.append("R2")
    if state.buttons.l3:             pressed.append("L3")
    if state.buttons.r3:             pressed.append("R3")
    if state.buttons.ps:             pressed.append("PS")
    if state.buttons.touchpad_click: pressed.append("TP")
    if state.buttons.mute:           pressed.append("MUT")
    if dpad != DPadDirection.NEUTRAL:
        pressed.append(f"D{dpad.name}")

    s.update({
        "forward":  forward,  "turn":  turn,  "boost": boost,
        "lw": lw,             "rw":    rw,
        "l2": state.l2,       "r2":    state.r2,
        "stopped":  stopped,
        "btns":     pressed,
        "gyro":     tuple(state.gyro),
        "accel":    tuple(state.accel),
        "tp0":      state.touchpad.finger0,
        "tp1":      state.touchpad.finger1,
        "battery":  state.battery.level,
        "charging": state.battery.charging,
    })

    _apply_triggers(ds)
    _render()

    if state.buttons.cross:
        ds.set_rumble(0, 0)
        ds.set_led(0, 0, 0)
        sys.exit(0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    with DualSense() as ds:
        cfg = DRIVE_MODES["NORMAL"]
        ds.set_led(*cfg["led"])
        ds.set_player_leds(cfg["leds"])
        ds.set_trigger_effect("right", TriggerEffect.feedback(start=0, force=90))
        ds.set_trigger_effect("left",  TriggerEffect.weapon(start=50, end=180, force=200))

        def _cb(state: InputState):
            on_state(state, ds)

        ds.listen(_cb)


if __name__ == "__main__":
    main()

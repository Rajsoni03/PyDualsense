#!/usr/bin/env python3
"""
asteroid_miner.py — Terminal arcade game using every DualSense feature.

Controller feature map
──────────────────────
  Lightbar       health colour (green→yellow→red), shield=blue, hit=red flash
  Player LEDs    remaining lives (1–3 LED patterns)
  Mic LED        shield active=ON, cooldown=BLINK, off=OFF
  Rumble         collision burst, mining vibration proportional to R2
  R2 adaptive    per-weapon feel (MINE/BLAST/LASER), VIBRATION boost, RIGID game-over
  L2 adaptive    WEAPON click (brake point), FEEDBACK when shield held, RIGID game-over
  Left stick     move ship
  Right stick    fine-aim direction (8 directions)
  L3             toggle gyro-tilt steering (tilt controller to steer ship)
  R2 analog      hold near asteroid to mine  (MINE weapon only)
  L2 analog      charge shield  (click feel at activation threshold)
  L1 / R1        rotate aim direction 45°
  △              fire in aim direction  (MINE=single, BLAST=3-way spread, LASER=piercing)
  ○              deploy bomb  (8 s cooldown, clears radius-5)
  □  hold        engine boost (faster movement, R2 vibrates)
  ✕              quit
  D-Pad ◄/►      cycle weapon: MINE → BLAST → LASER
  Gyro           L3 to toggle tilt-to-steer; X-axis tilt gauge shown on screen
  Touchpad       finger 0 shown as target reticle T on map; click = homing shot
  PS             pause / unpause
"""

import sys, os, time, random, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.input_report import InputState
from pydualsense.protocol.constants import DPadDirection, PlayerLED, MicLED
from pydualsense.features.triggers import TriggerEffect
from pydualsense.utils.deadzone import apply_deadzone_circular

random.seed(42)

# ── Layout ────────────────────────────────────────────────────────────────────
W, IW  = 80, 78          # box total / inner width
COLS   = 26              # map columns  (2 + COLS + (COLS-1)*2 = 3*COLS = 78 = IW)
ROWS   = 16              # map rows
DZ     = 0.12            # stick deadzone

# ── ANSI colours (standard Python, no external libs) ─────────────────────────
RST = "\033[0m"
_ANSI = {
    '@': "\033[1;36m",   # bold cyan       – player ship
    'S': "\033[1;34m",   # bold blue       – shielded player
    '*': "\033[31m",     # red             – small asteroid
    '#': "\033[1;31m",   # bold red        – medium asteroid
    'O': "\033[33m",     # yellow          – large asteroid
    '.': "\033[93m",     # bright yellow   – mine bullet
    'B': "\033[1;95m",   # bold magenta    – blast bullet
    '|': "\033[1;93m",   # bold br.yellow  – laser beam
    'H': "\033[1;36m",   # bold cyan       – homing bullet
    '+': "\033[1;32m",   # bold green      – health pickup
    '$': "\033[1;33m",   # bold yellow     – score pickup
    'X': "\033[1;31m",   # bold red        – explosion
    '!': "\033[1;31m",   # bold red        – hit effect
    'T': "\033[1;35m",   # bold magenta    – touchpad target reticle
}

def _cc(ch: str) -> str:
    """Wrap ch in ANSI colour code; visible terminal width is always 1."""
    c = _ANSI.get(ch)
    return f"{c}{ch}{RST}" if c else ch


# ── Tables ────────────────────────────────────────────────────────────────────
DIRS       = [(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1),(0,1),(1,1)]
DIR_GLYPH  = ['→','↗','↑','↖','←','↙','↓','↘']
WEAPONS    = ['MINE','BLAST','LASER']
SCORE_VAL  = {1: 10, 2: 25, 3: 50}
AST_GLYPH  = {1: '*', 2: '#', 3: 'O'}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bl(c: str) -> str:
    return f"│{c:<{IW}}│"

def _fbar(v: int, mx: int, w: int) -> str:
    f = min(int(v / mx * w), w)
    return f"[{'█'*f}{'░'*(w-f)}]"

def _fp(f) -> str:
    if f and f.active:
        return f"({f.x:4d},{f.y:3d})"   # 10 chars
    return "    -    "                   # 9 chars

def _dist_wrap(ax, ay, bx, by):
    dx = ax - bx;  dx -= COLS * round(dx / COLS)
    dy = ay - by;  dy -= ROWS * round(dy / ROWS)
    return math.hypot(dx, dy)

def _tilt_gauge(val: int, rng: int = 8000, w: int = 9) -> str:
    """ASCII tilt bar inside brackets; total width = w+2 chars."""
    pos = min(w - 1, max(0, round((val + rng) / (2 * rng) * (w - 1))))
    return "[" + "─" * pos + "●" + "─" * (w - 1 - pos) + "]"


# ── Game state ────────────────────────────────────────────────────────────────
_G: dict = {}

def _new_asteroids(n: int) -> list:
    out = []
    for _ in range(n):
        for _ in range(30):
            x = random.uniform(1, COLS - 2)
            y = random.uniform(1, ROWS - 2)
            if abs(x - COLS / 2) > 4 or abs(y - ROWS / 2) > 4:
                break
        size = random.choice([1, 1, 2, 2, 3])
        ang  = random.uniform(0, 2 * math.pi)
        spd  = random.uniform(0.04, 0.10)
        out.append({"x": x, "y": y,
                    "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd,
                    "size": size, "hp": size * 2, "mine_prog": 0.0})
    return out

def _init():
    _G.clear()
    _G.update({
        "px": float(COLS // 2), "py": float(ROWS // 2),
        "aim": 0, "hp": 100, "lives": 3, "score": 0, "frame": 0,
        "paused": False, "over": False,
        "weapon_idx": 0,
        "shield": False, "shield_cd": 0.0,
        "boosting": False,
        "mining": False, "mine_prog": 0.0, "mine_target": None,
        "bomb_cd": 0.0, "fire_cd": 0, "inv": 0,
        "gyro_steer": False,
        "asteroids": _new_asteroids(7),
        "bullets": [], "pickups": [], "effects": [],
        "msg": "L3=Gyro-Steer  D◄►=Weapon  TP=Homing", "msg_ttl": 120,
        # Controller (written by callback thread)
        "lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0,
        "l2": 0, "r2": 0,
        "btn_tri": False, "btn_cir": False, "btn_sq": False, "btn_x": False,
        "btn_l1": False, "btn_r1": False, "btn_l3": False,
        "btn_ps": False, "btn_tp": False,
        "dpad": DPadDirection.NEUTRAL,
        "gyro": (0, 0, 0), "accel": (0, 0, 0),
        "tp0": None, "tp1": None,
        "battery": 0, "charging": False,
        # One-shot pending flags (set by callback, consumed by tick)
        "fire_pend": False, "bomb_pend": False,
        "l1_pend":  False,  "r1_pend": False,
        "l3_pend":  False,
        "ps_pend":  False,  "tp_pend": False,
        "dpad_pend": DPadDirection.NEUTRAL,
        # Feedback tracking
        "_fb_key": None, "_led": None, "_pleds": None, "_mic": None,
    })


# ── Physics ───────────────────────────────────────────────────────────────────

def _spawn_pickup(x, y):
    r = random.random()
    if r < 0.15:
        _G["pickups"].append({"x": x, "y": y, "type": "+", "ttl": 160})
    elif r < 0.28:
        _G["pickups"].append({"x": x, "y": y, "type": "$", "ttl": 160})


def _fire():
    """Fire bullets based on current weapon selection."""
    g   = _G
    aim = g["aim"]
    w   = g["weapon_idx"]

    if w == 0:
        # MINE: single slow shot, enables R2 mining mode
        dx, dy = DIRS[aim]
        g["bullets"].append({
            "x": g["px"] + dx * 0.6, "y": g["py"] + dy * 0.6,
            "dx": float(dx) * 1.6,   "dy": float(dy) * 1.6,
            "ttl": 14, "glyph": '.', "pierce": False, "dmg": 1,
        })
        g["fire_cd"] = 8

    elif w == 1:
        # BLAST: 3-way spread (aim-1, aim, aim+1)
        for off in (-1, 0, 1):
            d  = (aim + off) % 8
            dx, dy = DIRS[d]
            g["bullets"].append({
                "x": g["px"] + dx * 0.5, "y": g["py"] + dy * 0.5,
                "dx": float(dx) * 1.4,   "dy": float(dy) * 1.4,
                "ttl": 11, "glyph": 'B', "pierce": False, "dmg": 1,
            })
        g["fire_cd"] = 6

    else:
        # LASER: single fast piercing beam (deals 2 damage, passes through)
        dx, dy = DIRS[aim]
        g["bullets"].append({
            "x": g["px"] + dx * 0.6, "y": g["py"] + dy * 0.6,
            "dx": float(dx) * 2.8,   "dy": float(dy) * 2.8,
            "ttl": 10, "glyph": '|', "pierce": True, "dmg": 2,
        })
        g["fire_cd"] = 12


def _fire_homing():
    g = _G
    f = g["tp0"]
    if not (f and f.active):
        _fire(); return
    tx = f.x / 1920.0 * COLS
    ty = f.y / 1080.0 * ROWS
    dx = tx - g["px"];  dy = ty - g["py"]
    dist = math.hypot(dx, dy) or 1.0
    g["bullets"].append({
        "x": g["px"], "y": g["py"],
        "dx": dx / dist * 1.8, "dy": dy / dist * 1.8,
        "ttl": 18, "glyph": 'H', "pierce": False, "dmg": 1,
    })
    g["fire_cd"] = 7
    g["msg"] = "Homing shot!"; g["msg_ttl"] = 30


def _bomb():
    g = _G
    cnt = 0
    for a in list(g["asteroids"]):
        if _dist_wrap(a["x"], a["y"], g["px"], g["py"]) < 5.0:
            g["asteroids"].remove(a)
            g["score"] += SCORE_VAL[a["size"]]
            g["effects"].append({"x": a["x"], "y": a["y"], "ch": "X", "ttl": 10})
            cnt += 1
    g["bomb_cd"] = 8.0
    g["effects"].append({"x": g["px"], "y": g["py"], "ch": "*", "ttl": 10})
    g["msg"] = f"BOMB! {cnt} destroyed"; g["msg_ttl"] = 50


def _die():
    g = _G
    g["lives"] -= 1
    if g["lives"] <= 0:
        g["over"] = True
        g["msg"] = "GAME OVER! Press X to quit."
    else:
        g["hp"] = 100;  g["px"] = COLS / 2;  g["py"] = ROWS / 2
        g["inv"] = 80;  g["msg"] = f"Respawn! Lives: {g['lives']}";  g["msg_ttl"] = 60


def _tick(dt: float):
    g = _G
    if g["over"]:
        return
    if g.pop("ps_pend", False):
        g["paused"] = not g["paused"]
    if g["paused"]:
        return

    g["frame"] += 1
    g["shield_cd"] = max(0.0, g["shield_cd"] - dt)
    g["bomb_cd"]   = max(0.0, g["bomb_cd"]   - dt)
    if g["fire_cd"] > 0: g["fire_cd"] -= 1
    if g["inv"]     > 0: g["inv"]     -= 1
    if g["msg_ttl"] > 0: g["msg_ttl"] -= 1

    # Gyro steer toggle
    if g.pop("l3_pend", False):
        g["gyro_steer"] = not g["gyro_steer"]
        g["msg"] = f"Gyro-Steer {'ON' if g['gyro_steer'] else 'OFF'}"; g["msg_ttl"] = 60

    # Sticks
    lx, ly = apply_deadzone_circular(g["lx"], g["ly"], DZ)
    rx, ry = apply_deadzone_circular(g["rx"], g["ry"], DZ)
    r2     = g["r2"] / 255.0
    l2     = g["l2"] / 255.0
    boost  = g["btn_sq"]
    spd    = 0.28 * (1.8 if boost else 1.0)

    # Movement (left stick)
    g["px"] = (g["px"] + lx * spd) % COLS
    g["py"] = (g["py"] + ly * spd) % ROWS
    g["boosting"] = boost

    # Gyro tilt-to-steer (L3 toggle): controller tilt moves ship
    if g["gyro_steer"]:
        gx, gy, gz = g["gyro"]
        g["px"] = (g["px"] + gx / 12000.0) % COLS
        g["py"] = (g["py"] + gy / 12000.0) % ROWS

    # Right-stick aim (negate ry: stick up = negative Y → atan2 should be positive)
    if abs(rx) > 0.55 or abs(ry) > 0.55:
        g["aim"] = round(math.atan2(-ry, rx) / (math.pi / 4)) % 8

    # L1/R1 aim rotation
    if g.pop("l1_pend", False): g["aim"] = (g["aim"] - 1) % 8
    if g.pop("r1_pend", False): g["aim"] = (g["aim"] + 1) % 8

    # D-pad weapon cycle
    d = g.pop("dpad_pend", DPadDirection.NEUTRAL)
    if d == DPadDirection.E:
        g["weapon_idx"] = (g["weapon_idx"] + 1) % len(WEAPONS)
        g["msg"] = f"Weapon: {WEAPONS[g['weapon_idx']]}"; g["msg_ttl"] = 50
    elif d == DPadDirection.W:
        g["weapon_idx"] = (g["weapon_idx"] - 1) % len(WEAPONS)
        g["msg"] = f"Weapon: {WEAPONS[g['weapon_idx']]}"; g["msg_ttl"] = 50

    # Shield
    g["shield"] = (l2 > 0.30 and g["shield_cd"] <= 0.0)

    # Mining: MINE weapon only — hold R2 near an asteroid
    mining = False;  target = None
    if r2 > 0.35 and not boost and g["weapon_idx"] == 0:
        best = 2.2
        for a in g["asteroids"]:
            d_val = _dist_wrap(a["x"], a["y"], g["px"], g["py"])
            if d_val < best:
                best, target = d_val, a
    if target:
        mining = True
        target["mine_prog"] += r2 * 0.07
        if target["mine_prog"] >= 1.0:
            g["asteroids"].remove(target)
            pts = SCORE_VAL[target["size"]] * 2
            g["score"] += pts
            _spawn_pickup(target["x"], target["y"])
            g["effects"].append({"x": target["x"], "y": target["y"], "ch": "X", "ttl": 8})
            g["msg"] = f"+{pts} mined!"; g["msg_ttl"] = 40
            target = None; mining = False
    g["mining"]      = mining
    g["mine_prog"]   = target["mine_prog"] if target else 0.0
    g["mine_target"] = target

    # Fire / bomb / homing
    if g.pop("fire_pend", False) and g["fire_cd"] <= 0: _fire()
    if g.pop("bomb_pend", False) and g["bomb_cd"] <= 0: _bomb()
    if g.pop("tp_pend",   False) and g["fire_cd"] <= 0: _fire_homing()

    # Move bullets, check asteroid hits
    for b in list(g["bullets"]):
        b["x"] += b["dx"];  b["y"] += b["dy"];  b["ttl"] -= 1
        if b["ttl"] <= 0 or not (0 <= b["x"] < COLS and 0 <= b["y"] < ROWS):
            try:    g["bullets"].remove(b)
            except ValueError: pass
            continue
        pierce = b.get("pierce", False)
        dmg    = b.get("dmg", 1)
        for a in list(g["asteroids"]):
            if math.hypot(b["x"] - a["x"], b["y"] - a["y"]) < 0.9:
                a["hp"] -= dmg
                if a["hp"] <= 0:
                    if a in g["asteroids"]: g["asteroids"].remove(a)
                    g["score"] += SCORE_VAL[a["size"]]
                    _spawn_pickup(a["x"], a["y"])
                    g["effects"].append({"x": a["x"], "y": a["y"], "ch": "X", "ttl": 6})
                if not pierce:
                    try:    g["bullets"].remove(b)
                    except ValueError: pass
                    break

    # Move asteroids
    for a in g["asteroids"]:
        a["x"] = (a["x"] + a["vx"]) % COLS
        a["y"] = (a["y"] + a["vy"]) % ROWS

    # Player–asteroid collision
    if g["inv"] <= 0:
        for a in list(g["asteroids"]):
            if _dist_wrap(a["x"], a["y"], g["px"], g["py"]) < 1.0:
                if g["shield"]:
                    g["shield"] = False;  g["shield_cd"] = 3.0;  g["inv"] = 20
                    g["effects"].append({"x": g["px"], "y": g["py"], "ch": "S", "ttl": 8})
                    g["msg"] = "Shield blocked!"; g["msg_ttl"] = 40
                else:
                    g["hp"] = max(0, g["hp"] - 25);  g["inv"] = 40
                    g["effects"].append({"x": g["px"], "y": g["py"], "ch": "!", "ttl": 8})
                    g["msg"] = f"HIT! HP:{g['hp']}"; g["msg_ttl"] = 40
                    if g["hp"] <= 0: _die()
                break

    # Pickups
    for p in list(g["pickups"]):
        p["ttl"] -= 1
        if p["ttl"] <= 0: g["pickups"].remove(p); continue
        if _dist_wrap(p["x"], p["y"], g["px"], g["py"]) < 1.2:
            if p["type"] == "+":
                g["hp"] = min(100, g["hp"] + 20)
                g["msg"] = "+20 HP!"; g["msg_ttl"] = 40
            else:
                g["score"] += 100
                g["msg"] = "+100 score!"; g["msg_ttl"] = 40
            g["pickups"].remove(p)

    # Decay effects
    for e in list(g["effects"]):
        e["ttl"] -= 1
        if e["ttl"] <= 0: g["effects"].remove(e)

    # Respawn asteroids
    if len(g["asteroids"]) < 3:
        g["asteroids"] += _new_asteroids(random.randint(2, 3))


# ── Feedback ──────────────────────────────────────────────────────────────────

def _feedback(ds: DualSense):
    g  = _G
    r2 = g["r2"] / 255.0

    # Triggers — update only on state change; per-weapon feel in normal state
    widx   = g["weapon_idx"]
    fb_key = ("over"    if g["over"]      else
              "boost"   if g["boosting"]  else
              "mining"  if g["mining"]    else
              "shield"  if g["shield"]    else
              f"w{widx}")

    if fb_key != g["_fb_key"]:
        g["_fb_key"] = fb_key
        if fb_key == "over":
            ds.set_trigger_effect("right", TriggerEffect.rigid())
            ds.set_trigger_effect("left",  TriggerEffect.rigid())
        elif fb_key == "boost":
            ds.set_trigger_effect("right", TriggerEffect.vibration(0, 160, 28))
            ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))
        elif fb_key == "mining":
            ds.set_trigger_effect("right", TriggerEffect.feedback(0, 210))
            ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))
        elif fb_key == "shield":
            ds.set_trigger_effect("right", TriggerEffect.feedback(0, 80))
            ds.set_trigger_effect("left",  TriggerEffect.feedback(0, 200))
        elif fb_key == "w1":  # BLAST: heavier pull, more resistance
            ds.set_trigger_effect("right", TriggerEffect.feedback(30, 140))
            ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))
        elif fb_key == "w2":  # LASER: slope feel — precision build-up
            ds.set_trigger_effect("right", TriggerEffect.slope(0, 200, 60, 220))
            ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))
        else:                 # w0 MINE: light resistive feedback
            ds.set_trigger_effect("right", TriggerEffect.feedback(0, 80))
            ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))

    # Rumble
    if g["over"]:
        ds.set_rumble(0, 0)
    elif g["inv"] > 25:
        ds.set_rumble(220, 150)
    elif g["mining"]:
        ds.set_rumble(int(r2 * 160), int(r2 * 80))
    elif g["boosting"]:
        ds.set_rumble(80, 40)
    else:
        ds.set_rumble(0, 0)

    # Lightbar — health colour, shield blue, hit flash, game-over off
    hp = g["hp"];  fr = g["frame"]
    if g["over"]:
        led = (0, 0, 0)
    elif g["inv"] > 0 and (g["inv"] % 6) < 3:
        led = (255, 0, 0)
    elif g["shield"]:
        led = (0, 100, 255)
    elif hp > 60:
        led = (0, 80 + int(hp * 1.2), 0)
    elif hp > 30:
        led = (200, 160, 0)
    else:
        p = int(abs(math.sin(fr * 0.15)) * 220)
        led = (p, 0, 0)
    if led != g["_led"]:
        g["_led"] = led;  ds.set_led(*led)

    # Player LEDs = lives
    pl = PlayerLED.player(g["lives"]) if g["lives"] > 0 else PlayerLED.NONE
    if pl != g["_pleds"]:
        g["_pleds"] = pl;  ds.set_player_leds(pl)

    # Mic LED = shield state
    mic = (MicLED.ON    if g["shield"]        else
           MicLED.BLINK if g["shield_cd"] > 0 else MicLED.OFF)
    if mic != g["_mic"]:
        g["_mic"] = mic;  ds.set_mic_led(mic)


# ── Rendering ─────────────────────────────────────────────────────────────────

def _build_map() -> list:
    grid = [[' '] * COLS for _ in range(ROWS)]
    for a in _G["asteroids"]:
        grid[int(a["y"]) % ROWS][int(a["x"]) % COLS] = AST_GLYPH.get(a["size"], '*')
    for p in _G["pickups"]:
        grid[int(p["y"]) % ROWS][int(p["x"]) % COLS] = p["type"]
    for e in _G["effects"]:
        grid[int(e["y"]) % ROWS][int(e["x"]) % COLS] = e["ch"]
    for b in _G["bullets"]:
        r, c = int(b["y"]) % ROWS, int(b["x"]) % COLS
        if grid[r][c] == ' ':
            grid[r][c] = b.get("glyph", '.')
    # Touchpad finger-0 target reticle
    f0 = _G["tp0"]
    if f0 and f0.active:
        tc = min(COLS - 1, max(0, int(f0.x / 1920.0 * COLS)))
        tr = min(ROWS - 1, max(0, int(f0.y / 1080.0 * ROWS)))
        if grid[tr][tc] == ' ':
            grid[tr][tc] = 'T'
    # Aim indicator (cell in aim direction, if empty)
    px, py = int(_G["px"]) % COLS, int(_G["py"]) % ROWS
    adx, ady = DIRS[_G["aim"]]
    ar, ac = (py + ady) % ROWS, (px + adx) % COLS
    if grid[ar][ac] == ' ': grid[ar][ac] = DIR_GLYPH[_G["aim"]]
    # Player (blink during invincibility frames)
    if _G["inv"] == 0 or (_G["inv"] % 4) < 3:
        grid[py][px] = 'S' if _G["shield"] else '@'
    return grid


def _render():
    g   = _G
    hp  = g["hp"];  fr = g["frame"]
    bm  = f"{g['bomb_cd']:.1f}s" if g["bomb_cd"] > 0 else "RDY"
    wep = WEAPONS[g["weapon_idx"]]
    aim = DIR_GLYPH[g["aim"]]
    sh  = "ON " if g["shield"] else ("CD " if g["shield_cd"] > 0 else "OFF")
    msg = (g["msg"] if g["msg_ttl"] > 0 else "")[:22]
    bat = ("~" if g["charging"] else " ")
    sts = "[PAUSED]" if g["paused"] else ("[OVER]  " if g["over"] else f"[Lv:{g['lives']}]   ")

    gx, gy, gz = g["gyro"]
    f0, f1     = g["tp0"], g["tp1"]

    gs_on = "ON " if g["gyro_steer"] else "OFF"
    tilt  = _tilt_gauge(gx)       # 11 chars  [─────●───]

    hp_bar = _fbar(hp, 100, 10)   # 12 chars  [██████░░░░]
    r2_bar = _fbar(g["r2"], 255, 6)
    l2_bar = _fbar(g["l2"], 255, 6)
    mn_bar = _fbar(int(g["mine_prog"] * 255), 255, 6) if g["mine_target"] else "[      ]"

    grid = _build_map()

    out = ["\033[H\033[J"]
    out.append("╔" + "═" * IW + "╗")
    out.append(_bl(f"  ASTEROID MINER  {sts}  Sc:{g['score']:06d}  {bat}Bat:{g['battery']:3d}%"))
    out.append("╠" + "═" * IW + "╣")
    out.append(_bl(f"  Hp:{hp_bar}{hp:3d}  Wep:{wep:<5}  Bm:{bm:<5}  {msg}"))
    out.append("╠" + "═" * IW + "╣")
    for row in grid:
        # ANSI-coloured row: visible width = 2 + COLS + (COLS-1)*2 = 3*COLS = 78 = IW
        colored_row = "  " + "  ".join(_cc(ch) for ch in row)
        out.append(f"│{colored_row}│")
    out.append("╠" + "═" * IW + "╣")
    out.append(_bl(f"  Aim:{aim}  Sh:{sh}  Mng:{mn_bar}  R2:{r2_bar}{g['r2']:3d}  L2:{l2_bar}{g['l2']:3d}"))
    out.append(_bl(f"  Gy:X{gx:+06d}Y{gy:+06d}  L3-Steer:{gs_on}{tilt}  F0:{_fp(f0)}"))
    out.append("╠" + "═" * IW + "╣")
    out.append(_bl("  △=Fire ○=Bomb □=Boost L1/R1=Aim D◄►=Wep TP=Homing L3=Gyro ✕=Quit"))
    out.append("╚" + "═" * IW + "╝")
    print("\n".join(out), end="", flush=True)


# ── Controller callback ───────────────────────────────────────────────────────

def _on_input(state: InputState):
    g = _G
    g["lx"], g["ly"] = state.left_stick.normalised()
    g["rx"], g["ry"] = state.right_stick.normalised()
    g["l2"] = state.l2;  g["r2"] = state.r2

    # Rising-edge one-shots
    if state.buttons.triangle      and not g["btn_tri"]: g["fire_pend"] = True
    if state.buttons.circle        and not g["btn_cir"]: g["bomb_pend"] = True
    if state.buttons.l1            and not g["btn_l1"]:  g["l1_pend"]  = True
    if state.buttons.r1            and not g["btn_r1"]:  g["r1_pend"]  = True
    if state.buttons.l3            and not g["btn_l3"]:  g["l3_pend"]  = True
    if state.buttons.ps            and not g["btn_ps"]:  g["ps_pend"]  = True
    if state.buttons.touchpad_click and not g["btn_tp"]: g["tp_pend"]  = True

    # D-pad rising edge
    d = state.dpad
    if d != g["dpad"] and d != DPadDirection.NEUTRAL:
        g["dpad_pend"] = d
    g["dpad"] = d

    # Held state
    g["btn_tri"] = state.buttons.triangle
    g["btn_cir"] = state.buttons.circle
    g["btn_sq"]  = state.buttons.square
    g["btn_x"]   = state.buttons.cross
    g["btn_l1"]  = state.buttons.l1
    g["btn_r1"]  = state.buttons.r1
    g["btn_l3"]  = state.buttons.l3
    g["btn_ps"]  = state.buttons.ps
    g["btn_tp"]  = state.buttons.touchpad_click

    # Sensors
    g["gyro"]     = tuple(state.gyro)
    g["accel"]    = tuple(state.accel)
    g["tp0"]      = state.touchpad.finger0
    g["tp1"]      = state.touchpad.finger1
    g["battery"]  = state.battery.level
    g["charging"] = state.battery.charging

    if state.buttons.cross:
        os._exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    _init()
    with DualSense() as ds:
        ds.set_led(0, 200, 0)
        ds.set_player_leds(PlayerLED.player(3))
        ds.set_trigger_effect("right", TriggerEffect.feedback(0, 80))
        ds.set_trigger_effect("left",  TriggerEffect.weapon(50, 150, 180))
        ds.listen_async(_on_input)

        dt = 1.0 / 20.0        # 20 fps game loop
        while True:
            t0 = time.monotonic()
            _tick(dt)
            _feedback(ds)
            _render()
            sleep = dt - (time.monotonic() - t0)
            if sleep > 0:
                time.sleep(sleep)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Halloween 2026 screensaver for Waveshare 11.9 displays (1480x320).

A dark graveyard nightscape rendered entirely with pygame primitives:
a spooky shaded moon with drifting clouds, twinkling stars, gnarled dead
trees, a cobwebbed server rack with blinking LEDs, a wandering spider and a
2RU mock Waveshare screen reading "happy halloween 2026", glowing carved
pumpkins with flickering candle light, drifting ground fog, flocks of
flapping bats, and a tilted granite tombstone engraved "R.I.P / miniracks"
whose lettering shimmers faintly in the moonlight. Both texts are
configurable (--tombstone-text, --screen-text).

Rare events (lightning, a rack kernel panic, a ghostly wisp, a shooting
star, owl eyes in the tree) fire every minute or three.

All heavy work (per-pixel shading, sprite generation, shimmer frames) is
done once at startup; the per-frame cost is a handful of small blits and
fills so it runs well on a Raspberry Pi. Optional artwork overrides may be
placed in an ``assets`` folder beside this file (see README); everything is
procedural when they are absent.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)
SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_DIR = SCRIPT_DIR / "assets"

try:
    import pygame
except ImportError:
    print(
        "Missing dependency: pygame\n\n"
        "Install with:\n"
        "  pip install -r requirements.txt\n\n"
        "On Raspberry Pi OS you may also need:\n"
        "  sudo apt update\n"
        "  sudo apt install python3-venv python3-pip libsdl2-2.0-0\n",
        file=sys.stderr,
    )
    sys.exit(1)

# --- Display (physical panel: 1480 wide x 320 tall) ---
SCREEN_W = 1480
SCREEN_H = 320

# --- Scene layout (full-resolution pixels; scaled by --render-scale) ---
HORIZON_Y = 238            # far hills meet the sky here
GROUND_Y = 246             # top of the foreground ground plane
MOON_POS = (1000, 86)
MOON_RADIUS = 60
RACK_RECT = (565, 52, 150, 196)          # x, y, w, h (bottom sits on the ground)
TOMBSTONE = (1265, 268, 124, 142)        # centre x, baseline y, w, h
TOMBSTONE_TILT = -3.5                    # degrees (negative leans right)
TOMBSTONE_LINES = ("R.I.P", "miniracks")     # CLI: --tombstone-text
SCREEN_TEXT = "happy halloween 2026"         # mock Waveshare panel in the rack; CLI: --screen-text
SCREEN_TEXT_COLOR = (255, 138, 28)
BACK_STONE = (1178, 258, 54, 64, 7.0)    # smaller stone behind-left: cx, base, w, h, tilt
TREE_LEFT = (118, 244, 205)              # x, base y, height
TREE_RIGHT = (1434, 250, 150)
OWL_OFFSET = (-4, -118)                  # owl eyes relative to the left tree base
PUMPKINS = (                             # centre x, baseline y, width, face template
    (300, 300, 108, 0),
    (438, 286, 64, 1),
    (812, 292, 86, 2),
    (1118, 302, 98, 3),
    (1392, 290, 70, 1),
    (62, 296, 80, 2),
)

# --- Timing (seconds; CLI: --bat-interval, --spider-interval, --rare-interval) ---
BAT_INTERVAL = (10.0, 25.0)
SPIDER_INTERVAL = (20.0, 50.0)
RARE_INTERVAL = (60.0, 180.0)
FOG_PERIOD = (45.0, 90.0)      # per-layer density cycle; fog is thin most of the time
SHIMMER_INTERVAL = (5.0, 11.0)
SHIMMER_DURATION = 2.4
ANIM_SPEED = 1.0               # CLI: --speed

# --- Motion (full-resolution px/s) ---
WIND_SPEED = 9.0               # cloud drift; fog layers scale from this
BAT_SPEED = (95.0, 175.0)
BAT_FLAP_HZ = (7.0, 11.0)
SPIDER_DESCEND_SPEED = 24.0
SPIDER_WALK_SPEED = 17.0
SPIDER_CLIMB_SPEED = 32.0

# --- Palette ---
SKY_TOP = (4, 4, 14)
SKY_MID = (24, 10, 42)
SKY_HORIZON = (44, 36, 54)
HAZE_COLOR = (70, 58, 82)
STAR_COLOR = (205, 205, 230)
MOON_BASE = (234, 216, 156)
MOON_TINT = (226, 160, 96)
MOON_HALO = (96, 72, 34)
HILL_FAR = (17, 13, 28)
HILL_NEAR = (11, 9, 17)
GROUND_TOP = (23, 21, 24)
GROUND_BOT = (7, 6, 9)
GRASS_COLORS = ((28, 36, 26), (20, 27, 20), (34, 40, 30))
TREE_COLOR = (9, 7, 12)
WEB_COLOR = (206, 206, 222)
SPIDER_COLOR = (12, 10, 14)
SPIDER_EYES = (190, 40, 40)
CLOUD_COLOR = (14, 10, 24)
FOG_COLOR = (142, 152, 172)
STONE_BASE = (98, 102, 108)
STONE_TEXT = (26, 26, 30)
STONE_TEXT_LIGHT = (134, 138, 146)
SHIMMER_COLOR = (222, 226, 236)
MOSS_COLOR = (46, 74, 40)
PUMPKIN_COLORS = ((228, 112, 24), (214, 98, 22), (236, 128, 36))
PUMPKIN_INNER = (36, 12, 4)
FACE_LIGHT = (255, 176, 66)
FACE_CORE = (255, 236, 176)
GLOW_COLOR = (96, 46, 10)
BAT_COLOR = (13, 10, 17)
FIREFLY_COLOR = (170, 220, 100)
WISP_COLOR = (150, 228, 180)
LED_GREEN = (70, 230, 90)
LED_AMBER = (255, 170, 40)
LED_RED = (236, 52, 40)
LED_BLUE = (80, 150, 255)

# --- Detail / performance presets ---
DETAIL_PRESETS = {
    "low": {"fog_layers": 2, "twinklers": 10, "clouds": 1, "flock": (3, 5),
            "fireflies": 0, "smooth": False},
    "medium": {"fog_layers": 3, "twinklers": 22, "clouds": 2, "flock": (4, 8),
               "fireflies": 12, "smooth": True},
    "high": {"fog_layers": 4, "twinklers": 36, "clouds": 3, "flock": (6, 12),
             "fireflies": 22, "smooth": True},
}

SHIMMER_FRAMES = 24
GLOW_LEVELS = 8
FLAP_SEQUENCE = (0, 1, 2, 3, 2, 1)

# Pumpkin face templates in unit body coordinates (u: 0..1 across, v: 0..1 down).
# Each entry is ("poly", [(u, v), ...]) or ("ellipse", (u, v, width, height)).
FACE_TEMPLATES = (
    (   # 0 classic grin
        ("poly", [(0.22, 0.46), (0.33, 0.28), (0.42, 0.46)]),
        ("poly", [(0.58, 0.46), (0.67, 0.28), (0.78, 0.46)]),
        ("poly", [(0.46, 0.60), (0.50, 0.50), (0.54, 0.60)]),
        ("poly", [(0.20, 0.66), (0.30, 0.72), (0.36, 0.66), (0.44, 0.74), (0.56, 0.74),
                  (0.64, 0.66), (0.70, 0.72), (0.80, 0.66), (0.72, 0.84), (0.60, 0.88),
                  (0.52, 0.80), (0.44, 0.88), (0.30, 0.84)]),
    ),
    (   # 1 evil squint
        ("poly", [(0.18, 0.40), (0.42, 0.46), (0.40, 0.56), (0.22, 0.52)]),
        ("poly", [(0.82, 0.40), (0.58, 0.46), (0.60, 0.56), (0.78, 0.52)]),
        ("poly", [(0.16, 0.68), (0.26, 0.64), (0.32, 0.70), (0.40, 0.63), (0.48, 0.71),
                  (0.56, 0.63), (0.64, 0.70), (0.72, 0.64), (0.84, 0.68), (0.76, 0.82),
                  (0.66, 0.86), (0.58, 0.79), (0.50, 0.88), (0.42, 0.79), (0.32, 0.86),
                  (0.22, 0.80)]),
    ),
    (   # 2 surprised
        ("ellipse", (0.32, 0.42, 0.18, 0.20)),
        ("ellipse", (0.68, 0.42, 0.18, 0.20)),
        ("poly", [(0.46, 0.62), (0.50, 0.52), (0.54, 0.62)]),
        ("ellipse", (0.50, 0.78, 0.22, 0.20)),
    ),
    (   # 3 goofy
        ("poly", [(0.20, 0.46), (0.32, 0.26), (0.44, 0.46)]),
        ("poly", [(0.58, 0.32), (0.78, 0.32), (0.78, 0.48), (0.58, 0.48)]),
        ("poly", [(0.18, 0.64), (0.40, 0.70), (0.62, 0.66), (0.84, 0.72), (0.70, 0.86),
                  (0.60, 0.80), (0.54, 0.92), (0.46, 0.80), (0.28, 0.84)]),
    ),
)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp_color(a, b, t: float) -> tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def scale_color(c, k: float) -> tuple[int, int, int]:
    return (
        int(clamp(c[0] * k, 0, 255)),
        int(clamp(c[1] * k, 0, 255)),
        int(clamp(c[2] * k, 0, 255)),
    )


def verify_runtime() -> None:
    if sys.version_info[:2] < MIN_PYTHON:
        major, minor = MIN_PYTHON
        print(
            f"Python {major}.{minor}+ is required (found {sys.version_info.major}."
            f"{sys.version_info.minor}).",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        print(
            "Warning: no DISPLAY or WAYLAND_DISPLAY - pygame needs a graphical session.\n"
            "Run from the Pi desktop, or enable autostart after graphical.target.",
            file=sys.stderr,
        )


def optional_asset(name: str) -> Path | None:
    """Return the path of an optional override asset beside this script, or None."""
    path = ASSET_DIR / name
    return path if path.is_file() else None


def load_optional_image(name: str) -> pygame.Surface | None:
    """Load assets/<name> if present; any failure falls back to procedural art."""
    path = optional_asset(name)
    if path is None:
        return None
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, OSError) as exc:
        print(f"Warning: could not load optional asset {path.name}: {exc}", file=sys.stderr)
        return None


# ------------------------------------------------------------ sprite helpers

def make_blob(rx: int, ry: int, color, peak_alpha: int, power: float = 1.6) -> pygame.Surface:
    """Soft elliptical alpha blob (transparent edge, peak_alpha centre)."""
    rx, ry = max(1, int(rx)), max(1, int(ry))
    surf = pygame.Surface((rx * 2 + 2, ry * 2 + 2), pygame.SRCALPHA)
    steps = max(3, min(rx, ry, 40))
    for i in range(steps):
        t = i / steps
        a = int(peak_alpha * (t ** power))
        if a <= 0:
            continue
        rect = pygame.Rect(0, 0, int(rx * 2 * (1 - t)) + 1, int(ry * 2 * (1 - t)) + 1)
        rect.center = (rx + 1, ry + 1)
        pygame.draw.ellipse(surf, (*color, a), rect)
    return surf


def make_glow_rgb(rx: int, ry: int, color, power: float = 2.0) -> pygame.Surface:
    """Radial RGB glow on black for additive blits (colour at centre, black edge)."""
    rx, ry = max(1, int(rx)), max(1, int(ry))
    surf = pygame.Surface((rx * 2 + 2, ry * 2 + 2))
    steps = max(3, min(rx, ry, 48))
    for i in range(steps):
        t = i / steps
        c = scale_color(color, t ** power)
        if max(c) == 0:
            continue
        rect = pygame.Rect(0, 0, int(rx * 2 * (1 - t)) + 1, int(ry * 2 * (1 - t)) + 1)
        rect.center = (rx + 1, ry + 1)
        pygame.draw.ellipse(surf, c, rect)
    return surf


def unit_poly(shape, w: int, h: int, ox: int = 0, oy: int = 0, inset: float = 0.0):
    """Convert a face template shape into pixel points / rect, optionally shrunk."""
    kind, data = shape
    if kind == "poly":
        pts = [(u * w, v * h) for u, v in data]
        if inset:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            pts = [(cx + (x - cx) * (1 - inset), cy + (y - cy) * (1 - inset)) for x, y in pts]
        return "poly", [(ox + x, oy + y) for x, y in pts]
    u, v, uw, vh = data
    rw, rh = uw * w * (1 - inset), vh * h * (1 - inset)
    rect = pygame.Rect(0, 0, max(1, int(rw)), max(1, int(rh)))
    rect.center = (int(ox + u * w), int(oy + v * h))
    return "ellipse", rect


def draw_shape(surf: pygame.Surface, color, shape) -> None:
    kind, data = shape
    if kind == "poly":
        pygame.draw.polygon(surf, color, data)
    else:
        pygame.draw.ellipse(surf, color, data)


# ----------------------------------------------------------- scene builders

def build_moon(r: int, rng: random.Random) -> pygame.Surface:
    """Per-pixel shaded moon disc: limb darkening, craters with lit rims, tint."""
    size = r * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # Three broad, shallow "maria" plus a scatter of small, deeper craters.
    craters = []
    for _ in range(3):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(0.1, 0.5) * r
        craters.append((math.cos(ang) * dist, math.sin(ang) * dist,
                        rng.uniform(0.28, 0.42) * r, rng.uniform(0.05, 0.09)))
    for _ in range(14):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(0.0, 0.82) * r
        cr = rng.uniform(0.04, 0.12) * r
        craters.append((math.cos(ang) * dist, math.sin(ang) * dist, cr, rng.uniform(0.12, 0.26)))
    cx = cy = r + 1
    for py in range(size):
        dy = py - cy
        for px in range(size):
            dx = px - cx
            d = math.hypot(dx, dy)
            if d > r + 0.5:
                continue
            alpha = int(255 * clamp(r + 0.5 - d, 0.0, 1.0))
            nd = d / r
            f = 1.0 - 0.34 * nd ** 4
            f *= 0.93 + 0.07 * (-(dx + dy) / (r * 1.4))
            for kx, ky, kr, depth in craters:
                dd = math.hypot(dx - kx, dy - ky) / kr
                if dd < 1.0:
                    f *= 1.0 - depth * (1.0 - dd * dd)
                elif depth > 0.1 and dd < 1.2 and (dx - kx) + (dy - ky) > 0:
                    f *= 1.06
            tint = clamp(dy / r, 0.0, 1.0) * 0.38
            base = lerp_color(MOON_BASE, MOON_TINT, tint)
            noise = rng.uniform(-5, 5)
            col = (
                int(clamp(base[0] * f + noise, 0, 255)),
                int(clamp(base[1] * f + noise, 0, 255)),
                int(clamp(base[2] * f + noise, 0, 255)),
            )
            surf.set_at((px, py), (*col, alpha))
    return surf


def hill_y(x: float, w: float, base: float, amp: float, offs) -> float:
    u = x / w * math.tau
    return base - amp * (
        0.5 * math.sin(u * 1.3 + offs[0])
        + 0.3 * math.sin(u * 3.1 + offs[1])
        + 0.2 * math.sin(u * 6.7 + offs[2])
    )


def draw_branch(surf, x, y, ang, length, width, depth, rng, color) -> None:
    if depth == 0 or length < 2.5:
        return
    mid_ang = ang + rng.uniform(-0.28, 0.28)
    mx = x + math.cos(mid_ang) * length * 0.5
    my = y + math.sin(mid_ang) * length * 0.5
    end_ang = ang + rng.uniform(-0.32, 0.32)
    ex = mx + math.cos(end_ang) * length * 0.5
    ey = my + math.sin(end_ang) * length * 0.5
    pygame.draw.line(surf, color, (x, y), (mx, my), max(1, int(width)))
    pygame.draw.line(surf, color, (mx, my), (ex, ey), max(1, int(width * 0.8)))
    n = 2 if rng.random() < 0.7 else 3
    for i in range(n):
        spread = rng.uniform(0.3, 0.95) * (1 if i % 2 == 0 else -1)
        draw_branch(surf, ex, ey, ang + spread, length * rng.uniform(0.58, 0.78),
                    width * 0.66, depth - 1, rng, color)


def draw_tree(bg: pygame.Surface, x: int, base_y: int, height: int, rng: random.Random) -> None:
    """Gnarled dead-tree silhouette: flared trunk plus recursive twisting branches."""
    ov = pygame.Surface(bg.get_size(), pygame.SRCALPHA)
    tw = max(3, height * 0.11)
    trunk_top = base_y - height * 0.42
    pygame.draw.polygon(ov, TREE_COLOR, [
        (x - tw * 1.6, base_y + 2), (x - tw * 0.55, base_y - height * 0.08),
        (x - tw * 0.42, trunk_top), (x + tw * 0.42, trunk_top),
        (x + tw * 0.6, base_y - height * 0.1), (x + tw * 1.7, base_y + 2),
    ])
    draw_branch(ov, x, trunk_top + 2, -math.pi / 2 + rng.uniform(-0.2, 0.2),
                height * 0.34, tw * 0.9, 5, rng, TREE_COLOR)
    for side in (-1, 1):
        ang = -math.pi / 2 + side * rng.uniform(0.55, 0.95)
        draw_branch(ov, x + side * tw * 0.3, base_y - height * rng.uniform(0.26, 0.4),
                    ang, height * 0.26, tw * 0.6, 4, rng, TREE_COLOR)
    bg.blit(ov, (0, 0))


def draw_cobweb(bg: pygame.Surface, cx: int, cy: int, radius: int, a0: float, a1: float,
                rng: random.Random) -> None:
    """Quadrant cobweb: spokes plus sagging, occasionally torn ring threads."""
    r = max(4, radius)
    local = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    c = (r + 2, r + 2)
    spokes = 7
    angles = []
    for i in range(spokes):
        a = a0 + (a1 - a0) * i / (spokes - 1)
        if 0 < i < spokes - 1:
            a += rng.uniform(-0.05, 0.05)
        angles.append(a)
    for a in angles:
        ln = r * rng.uniform(0.9, 1.05)
        pygame.draw.line(local, (*WEB_COLOR, 118), c,
                         (c[0] + math.cos(a) * ln, c[1] + math.sin(a) * ln))
    rings = 6
    for k in range(1, rings + 1):
        rr = r * (k / rings) ** 1.15
        for i in range(spokes - 1):
            if rng.random() < 0.12:
                continue
            pa = (c[0] + math.cos(angles[i]) * rr, c[1] + math.sin(angles[i]) * rr)
            pb = (c[0] + math.cos(angles[i + 1]) * rr, c[1] + math.sin(angles[i + 1]) * rr)
            mx = c[0] + ((pa[0] + pb[0]) / 2 - c[0]) * 0.9
            my = c[1] + ((pa[1] + pb[1]) / 2 - c[1]) * 0.9
            pygame.draw.lines(local, (*WEB_COLOR, 92), False, [pa, (mx, my), pb])
    for _ in range(5):
        a = rng.choice(angles)
        rr = r * rng.uniform(0.3, 0.95)
        local.set_at((int(c[0] + math.cos(a) * rr), int(c[1] + math.sin(a) * rr)),
                     (240, 240, 252, 210))
    bg.blit(local, (cx - r - 2, cy - r - 2))


class Led:
    __slots__ = ("x", "y", "w", "h", "kind", "color", "rate", "phase", "idx")

    def __init__(self, x, y, w, h, kind, color, rate, phase) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h
        self.kind, self.color, self.rate, self.phase = kind, color, rate, phase
        self.idx = 0


def build_rack(w: int, h: int, p, rng: random.Random, make_font,
               screen_text: str) -> tuple[pygame.Surface, list[Led], dict | None]:
    """Server rack face.

    Returns the sprite, the LED list and the mock Waveshare screen unit
    (``{"content": Surface, "pos": (x, y)}``); all positions are rack-local.
    """
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    leds: list[Led] = []
    screen: dict | None = None
    one = max(1, p(1))
    pygame.draw.rect(surf, (30, 32, 38), (0, 0, w, h), border_radius=p(3))
    pygame.draw.rect(surf, (64, 68, 78), (0, 0, w, h), width=one, border_radius=p(3))
    surf.fill((44, 46, 54), (one, one, w - 2 * one, p(5)))
    inset_x, inset_top, inset_bot = p(9), p(8), p(12)
    cav = pygame.Rect(inset_x, inset_top, w - 2 * inset_x, h - inset_top - inset_bot)
    pygame.draw.rect(surf, (9, 9, 13), cav)
    rail_w = p(4)
    for rx in (cav.left, cav.right - rail_w):
        pygame.draw.rect(surf, (50, 54, 62), (rx, cav.top, rail_w, cav.height))
        yy = cav.top + p(3)
        while yy < cav.bottom - p(2):
            surf.fill((20, 22, 26), (rx + one, yy, max(1, rail_w - 2 * one), max(1, p(2))))
            yy += p(6)

    def led(x, y, kind, color, rate=1.0, bw=3, bh=2):
        surf.fill((16, 16, 18), (x - one, y - one, p(bw) + 2 * one, p(bh) + 2 * one))
        leds.append(Led(x, y, max(1, p(bw)), max(1, p(bh)), kind, color, rate,
                        rng.uniform(0, 100)))

    ux = cav.left + rail_w + one
    uw = cav.width - 2 * rail_w - 2 * one
    yy = cav.top + p(2)
    plan = ["server", "server", "storage", "server", "switch", "blank", "server",
            "server", "storage", "server", "server"]
    i = 0
    while yy < cav.bottom - p(6):
        kind = plan[i % len(plan)] if rng.random() < 0.75 else rng.choice(plan)
        i += 1
        if screen is None and screen_text and yy >= cav.top + cav.height * 0.4:
            kind = "screen"      # 2RU mock Waveshare display about halfway down
        uh = {"server": p(14), "storage": p(40), "switch": p(18), "blank": p(10),
              "screen": p(30)}[kind]
        if yy + uh > cav.bottom - p(2):
            uh = cav.bottom - p(2) - yy
            kind = "blank"
        if uh < p(5):
            break
        face = rng.choice(((52, 56, 64), (46, 50, 58), (58, 62, 70)))
        dead = rng.random() < 0.15
        pygame.draw.rect(surf, face, (ux, yy, uw, uh))
        surf.fill((80, 84, 94), (ux, yy, uw, one))
        surf.fill((22, 24, 28), (ux, yy + uh - one, uw, one))
        if kind == "server":
            pygame.draw.rect(surf, (36, 38, 44), (ux + p(2), yy + p(2), p(10), uh - p(4)))
            ly = yy + uh // 2 - one
            lx = ux + p(15)
            if not dead:
                led(lx, ly, "power", LED_GREEN)
                led(lx + p(5), ly, "act", LED_AMBER, rng.uniform(5.0, 9.0))
                led(lx + p(10), ly, "net", LED_GREEN, rng.uniform(2.0, 6.0))
                if rng.random() < 0.22:
                    led(lx + p(15), ly, "fault", LED_RED, 0.7)
            if rng.random() < 0.5:
                gx = ux + int(uw * 0.46)
                for row in range(2):
                    gy = yy + p(4) + row * p(5)
                    xx = gx
                    while xx < ux + uw - p(4):
                        surf.fill((28, 30, 36), (xx, gy, one, one))
                        xx += p(3)
            else:
                bw = p(16)
                for k in range(2):
                    bx = ux + uw - p(4) - (k + 1) * (bw + p(2))
                    pygame.draw.rect(surf, (38, 40, 46), (bx, yy + p(3), bw, uh - p(6)))
                    if not dead:
                        led(bx + bw - p(4), yy + uh // 2 - one, "hdd",
                            rng.choice((LED_GREEN, LED_BLUE)), rng.uniform(0.6, 1.8), 2, 2)
        elif kind == "storage":
            cols, sled_h = 3, p(9)
            rows = max(1, (uh - p(4)) // sled_h)
            sled_w = (uw - p(6)) // cols
            for r in range(rows):
                for cidx in range(cols):
                    sx = ux + p(3) + cidx * sled_w
                    sy = yy + p(2) + r * sled_h
                    pygame.draw.rect(surf, (40, 42, 48), (sx, sy, sled_w - one, sled_h - one))
                    surf.fill((60, 62, 70), (sx, sy, sled_w - one, one))
                    if not dead and rng.random() < 0.8:
                        led(sx + sled_w - p(4), sy + sled_h // 2 - one, "hdd",
                            rng.choice((LED_GREEN, LED_GREEN, LED_AMBER)),
                            rng.uniform(0.5, 2.0), 2, 2)
        elif kind == "switch":
            port = p(4)
            n = max(4, int(uw * 0.72 / (port + p(2))))
            px0 = ux + p(6)
            for k in range(n):
                sx = px0 + k * (port + p(2))
                pygame.draw.rect(surf, (18, 18, 22), (sx, yy + uh - port - p(3), port, port))
                if not dead and rng.random() < 0.6:
                    led(sx, yy + p(3), "net", rng.choice((LED_GREEN, LED_AMBER)),
                        rng.uniform(3.0, 12.0), 3, 2)
            pygame.draw.rect(surf, (36, 38, 44), (ux + uw - p(14), yy + p(2), p(12), uh - p(4)))
        elif kind == "screen":
            # Rack-mounted wide panel: black bezel, dark glass with a warm glow,
            # scanlines, and a tiny power LED. The text is animated per frame.
            bezel = pygame.Rect(ux + p(4), yy + p(3), uw - p(8), uh - p(6))
            pygame.draw.rect(surf, (12, 12, 16), bezel, border_radius=p(2))
            pygame.draw.rect(surf, (40, 42, 50), bezel, width=one, border_radius=p(2))
            panel = bezel.inflate(-2 * p(3), -2 * p(3))
            pygame.draw.rect(surf, (7, 5, 11), panel)
            glow = make_glow_rgb(panel.width // 2, panel.height // 2 + p(2), (60, 28, 6), 1.4)
            surf.blit(glow, glow.get_rect(center=panel.center), special_flags=pygame.BLEND_RGB_ADD)
            for gy in range(panel.top, panel.bottom, max(2, p(2))):
                surf.fill((4, 3, 7), (panel.left, gy, panel.width, one))
            surf.fill((200, 210, 230), (bezel.right - p(4), bezel.bottom - p(3), one, one))
            font = shrink_font(make_font, screen_text, p(16), panel.width - p(4))
            text = font.render(screen_text, True, SCREEN_TEXT_COLOR)
            halo = font.render(screen_text, True, scale_color(SCREEN_TEXT_COLOR, 0.6))
            halo.set_alpha(150)
            content = pygame.Surface(panel.size, pygame.SRCALPHA)
            trect = text.get_rect(center=(panel.width // 2, panel.height // 2))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                content.blit(halo, (trect.x + dx, trect.y + dy))
            content.blit(text, trect.topleft)
            lines_mask = pygame.Surface(panel.size, pygame.SRCALPHA)
            lines_mask.fill((255, 255, 255, 255))
            for gy in range(0, panel.height, max(2, p(2))):
                lines_mask.fill((255, 255, 255, 190), (0, gy, panel.width, one))
            content.blit(lines_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen = {"content": content, "pos": panel.topleft}
        else:
            gy = yy + p(2)
            while gy < yy + uh - p(2):
                surf.fill((30, 32, 36), (ux + p(6), gy, uw - p(12), one))
                gy += p(3)
        yy += uh + p(2)

    # Draped cables along the right rail.
    for color, off in (((128, 80, 30), 0), ((30, 62, 124), p(3)), ((92, 92, 104), p(6))):
        pts = [(cav.right - rail_w - p(2) + off, cav.top + p(22) + off)]
        for k in range(1, 6):
            pts.append((cav.right - p(2) + off + rng.uniform(-p(2), p(2)),
                        cav.top + p(22) + (h - cav.top - p(22)) * k / 5))
        pygame.draw.lines(surf, color, False, pts, max(1, p(2)))

    # Dust and rust on an overlay (translucent strokes must be blitted, not drawn).
    ov = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(26):
        rect = pygame.Rect(rng.randint(0, w - 1), rng.randint(0, h - 1), p(rng.randint(6, 18)),
                           p(rng.randint(3, 8)))
        pygame.draw.ellipse(ov, (0, 0, 0, rng.randint(30, 60)), rect)
    for _ in range(3):
        rx = rng.randint(p(4), w - p(6))
        pygame.draw.line(ov, (96, 54, 30, 70), (rx, h - p(rng.randint(30, 70))), (rx, h - p(4)),
                         max(1, p(2)))
    surf.blit(ov, (0, 0))
    surf.fill((74, 78, 90), (w - 2 * one, p(3), one, h - p(6)))      # moonlit right edge
    return surf, leds, screen


def shrink_font(make_font, text: str, size: int, max_w: int) -> pygame.font.Font:
    while size > 8:
        font = make_font(size)
        if font.size(text)[0] <= max_w:
            return font
        size -= 1
    return make_font(8)


def build_tombstone(w: int, h: int, p, rng: random.Random, make_font,
                    override: pygame.Surface | None,
                    lines: tuple[str, ...]) -> tuple[pygame.Surface, list[pygame.Surface]]:
    """Tilted granite stone with engraved text. Returns (stone, shimmer frames)."""
    pad = p(10)
    sw, sh = w + pad * 2, h + pad * 2
    stone = pygame.Surface((sw, sh), pygame.SRCALPHA)
    if override is not None:
        stone.blit(pygame.transform.smoothscale(override, (w, h)), (pad, pad))
    else:
        top_h = int(h * 0.6)
        pygame.draw.ellipse(stone, (255, 255, 255, 255), (pad, pad, w, top_h))
        pygame.draw.rect(stone, (255, 255, 255, 255), (pad, pad + top_h // 2, w, h - top_h // 2))
        for py in range(pad, pad + h):
            v = (py - pad) / h
            for px in range(pad, pad + w):
                if stone.get_at((px, py))[3] == 0:
                    continue
                u = (px - pad) / w
                f = 1.0 + 0.2 * (1 - v) - 0.25 * v - 0.12 * u
                n = rng.uniform(-9, 9)
                if rng.random() < 0.05:
                    n += rng.uniform(8, 20)
                col = (
                    int(clamp(STONE_BASE[0] * f + n, 0, 255)),
                    int(clamp(STONE_BASE[1] * f + n, 0, 255)),
                    int(clamp(STONE_BASE[2] * f + n, 0, 255)),
                )
                stone.set_at((px, py), (*col, 255))
        # Chip out of the top-left edge (transparent erase).
        pygame.draw.circle(stone, (0, 0, 0, 0), (pad + int(w * 0.17), pad + int(h * 0.1)), p(5))
        # Crack from the upper right.
        cx, cy = pad + int(w * 0.72), pad + int(h * 0.04)
        pts = [(cx, cy)]
        while cy < pad + int(h * 0.62):
            cx += rng.randint(-p(6), p(4))
            cy += rng.randint(p(5), p(12))
            pts.append((cx, cy))
        pygame.draw.lines(stone, (40, 42, 46), False, pts, max(1, p(2)))
        pygame.draw.lines(stone, (124, 128, 136), False, [(x + 1, y + 1) for x, y in pts], 1)
        # Moss near the base and left side.
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for _ in range(26):
            mx = pad + int(w * rng.choice((rng.uniform(0, 0.25), rng.uniform(0, 1))))
            my = pad + int(h * rng.uniform(0.7, 1.0))
            blob = make_blob(p(rng.randint(5, 12)), p(rng.randint(3, 7)), MOSS_COLOR,
                             rng.randint(120, 200), 1.2)
            ov.blit(blob, blob.get_rect(center=(mx, my)))
        stone.blit(ov, (0, 0))
        # Rims: lighter top-left (moonlit), darker bottom-right.
        pygame.draw.arc(stone, (150, 154, 162), (pad, pad, w, top_h), math.radians(60),
                        math.radians(175), max(1, p(2)))
        pygame.draw.arc(stone, (44, 46, 52), (pad, pad, w, top_h), math.radians(5),
                        math.radians(60), max(1, p(2)))
        pygame.draw.line(stone, (46, 48, 54), (pad + w - 1, pad + top_h // 2),
                         (pad + w - 1, pad + h - 1), max(1, p(2)))
        pygame.draw.line(stone, (56, 58, 64), (pad, pad + h - 1), (pad + w, pad + h - 1),
                         max(1, p(2)))

    # Engraved text and the shimmer frames (same size as the stone, rotated alike).
    # Lines are centred in the upper two thirds of the stone, spaced to fit.
    line_specs = []
    lines = tuple(ln for ln in lines if ln.strip()) or TOMBSTONE_LINES
    n = len(lines)
    step = min(0.24, 0.5 / max(1, n - 1)) if n > 1 else 0.0
    y_frac = 0.30 if n <= 2 else 0.42 - step * (n - 1) / 2
    for idx, text in enumerate(lines):
        size = p(40 if idx == 0 else 34)
        if n > 2:
            size = p(max(16, 34 - 4 * (n - 2)))
        font = shrink_font(make_font, text, size, int(w * 0.84))
        dark = font.render(text, True, STONE_TEXT)
        light = font.render(text, True, STONE_TEXT_LIGHT)
        rect = dark.get_rect(center=(pad + w // 2, pad + int(h * y_frac)))
        stone.blit(light, (rect.x + 1, rect.y + 1))
        stone.blit(dark, rect.topleft)
        line_specs.append((font, text, rect))
        y_frac += step

    frames = []
    for i in range(SHIMMER_FRAMES):
        frame = pygame.Surface((sw, sh), pygame.SRCALPHA)
        sweep = -0.25 + 1.5 * i / (SHIMMER_FRAMES - 1)
        for font, text, rect in line_specs:
            hl = font.render(text, True, SHIMMER_COLOR)
            mask = pygame.Surface(hl.get_size(), pygame.SRCALPHA)
            tw = hl.get_width()
            sigma = max(2.0, tw * 0.13)
            sx = sweep * tw
            for x in range(tw):
                a = int(255 * math.exp(-((x - sx) ** 2) / (2 * sigma * sigma)))
                if a:
                    mask.fill((255, 255, 255, a), (x, 0, 1, hl.get_height()))
            hl.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            frame.blit(hl, rect.topleft)
        frames.append(pygame.transform.rotate(frame, TOMBSTONE_TILT))
    return pygame.transform.rotate(stone, TOMBSTONE_TILT), frames


def build_small_stone(w: int, h: int, tilt: float, p, rng: random.Random) -> pygame.Surface:
    surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
    col = (58, 60, 66)
    pygame.draw.ellipse(surf, col, (2, 2, w, int(h * 0.55)))
    pygame.draw.rect(surf, col, (2, 2 + int(h * 0.27), w, h - int(h * 0.27)))
    pygame.draw.rect(surf, (36, 38, 42), (2 + w // 2 - p(3), 2 + int(h * 0.22), p(6), int(h * 0.5)))
    pygame.draw.rect(surf, (36, 38, 42), (2 + w // 2 - p(10), 2 + int(h * 0.32), p(20), p(5)))
    for _ in range(40):
        x, y = rng.randint(2, w), rng.randint(2, h)
        if surf.get_at((x, y))[3]:
            surf.set_at((x, y), (*lerp_color(col, (90, 92, 98), rng.random()), 255))
    return pygame.transform.rotate(surf, tilt)


def build_pumpkin(w: int, face_id: int, p, rng: random.Random):
    """Returns (body sprite, face-light sprite, glow levels, draw offset of the body)."""
    h = int(w * 0.78)
    stem_h = int(w * 0.22)
    sw, sh = w + 4, h + stem_h + 4
    body = pygame.Surface((sw, sh), pygame.SRCALPHA)
    ox, oy = 2, stem_h + 2
    base = rng.choice(PUMPKIN_COLORS)
    dark = lerp_color(base, (60, 20, 6), 0.55)
    lobes = 5
    for k in range(lobes):
        c = abs(k - lobes // 2)
        lw = int(w * (0.42 - 0.07 * c))
        lh = int(h * (1.0 - 0.05 * c))
        lx = ox + w // 2 + int((k - lobes // 2) * w * 0.17)
        rect = pygame.Rect(0, 0, lw, lh)
        rect.center = (lx, oy + h // 2 + (h - lh) // 2)
        pygame.draw.ellipse(body, lerp_color(base, dark, 0.12 * c), rect)
        pygame.draw.ellipse(body, lerp_color(base, dark, 0.65), rect, max(1, p(1)))
    # Shading overlay: darker base and sides for roundness, soft top-left highlight.
    ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for yy in range(oy, oy + h):
        t = (yy - oy) / h
        a = int(120 * max(0.0, t - 0.4) / 0.6)
        if a:
            ov.fill((40, 10, 0, a), (ox, yy, w, 1))
    side = pygame.Surface((sw, sh), pygame.SRCALPHA)
    ew = max(2, int(w * 0.3))
    for xx in range(ew):
        a = int(105 * (1 - xx / ew) ** 1.6)
        side.fill((30, 6, 0, a), (ox + xx, oy, 1, h))
        side.fill((30, 6, 0, int(a * 1.25)), (ox + w - 1 - xx, oy, 1, h))
    ov.blit(side, (0, 0))
    hl = make_blob(int(w * 0.26), int(h * 0.18), (255, 210, 150), 85, 1.3)
    ov.blit(hl, hl.get_rect(center=(ox + int(w * 0.34), oy + int(h * 0.2))))
    mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255, 255), (ox, oy, w, h))
    ov.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    body.blit(ov, (0, 0))
    # Carved face: dark interior with a thin scorched edge.
    template = FACE_TEMPLATES[face_id % len(FACE_TEMPLATES)]
    for shape in template:
        draw_shape(body, (112, 44, 10), unit_poly(shape, w, h, ox, oy, -0.08))
        draw_shape(body, PUMPKIN_INNER, unit_poly(shape, w, h, ox, oy))
    # Stem and tendril.
    sx = ox + w // 2
    stem = [(sx - p(5), oy + p(3)), (sx - p(4), 2), (sx + p(4), 3), (sx + p(6), oy + p(3))]
    pygame.draw.polygon(body, (78, 86, 42), stem)
    pygame.draw.line(body, (48, 56, 26), (sx + p(2), 3), (sx + p(4), oy + p(2)), max(1, p(2)))
    pygame.draw.arc(body, (74, 104, 50), (sx + p(4), 2, p(14), p(12)), math.pi * 0.2, math.pi * 1.3,
                    max(1, p(1)))

    face = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for shape in template:
        draw_shape(face, (*FACE_LIGHT, 110), unit_poly(shape, w, h, ox, oy, -0.10))
    for shape in template:
        draw_shape(face, (*FACE_LIGHT, 255), unit_poly(shape, w, h, ox, oy))
    for shape in template:
        draw_shape(face, (*FACE_CORE, 255), unit_poly(shape, w, h, ox, oy, 0.45))

    glow = make_glow_rgb(int(w * 1.25), int(w * 0.5), GLOW_COLOR, 2.2)
    levels = []
    for i in range(GLOW_LEVELS):
        k = int(255 * (i + 1) / GLOW_LEVELS)
        g = glow.copy()
        g.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
        levels.append(g)
    return body, face, levels, (ox, oy, w, h)


def build_bat_frames(size: int, p) -> list[pygame.Surface]:
    """Four wing positions of a symmetric bat silhouette, size = wingspan px."""
    frames = []
    half = size / 2
    sh = int(size * 0.55) + 2
    for k in (1.0, 0.45, -0.1, -0.6):
        surf = pygame.Surface((size + 2, sh), pygame.SRCALPHA)
        cx, cy = half + 1, sh * 0.5
        body_w, body_h = max(2, int(size * 0.13)), max(3, int(size * 0.3))
        pygame.draw.ellipse(surf, BAT_COLOR, (cx - body_w / 2, cy - body_h / 2, body_w, body_h))
        head_r = max(1, int(size * 0.07))
        pygame.draw.circle(surf, BAT_COLOR, (cx, cy - body_h / 2), head_r)
        for s in (-1, 1):
            pygame.draw.polygon(surf, BAT_COLOR, [
                (cx + s * head_r * 0.3, cy - body_h / 2 - head_r * 0.6),
                (cx + s * head_r * 1.1, cy - body_h / 2 - head_r * 2.2),
                (cx + s * head_r * 1.2, cy - body_h / 2 - head_r * 0.2),
            ])
            wing = [
                (0.0, 0.0), (0.27, -0.30 * k), (0.62, -0.42 * k), (1.0, -0.30 * k),
                (0.86, 0.10 - 0.12 * k), (0.60, 0.16 - 0.08 * k), (0.32, 0.20 - 0.04 * k),
                (0.08, 0.16),
            ]
            pts = [(cx + s * ux * half, cy - body_h * 0.15 + vy * half) for ux, vy in wing]
            pygame.draw.polygon(surf, BAT_COLOR, pts)
        frames.append(surf)
    return frames


def build_cloud(w: int, h: int, p, rng: random.Random) -> pygame.Surface:
    """Dark wispy cloud; the sprite is padded so no blob is clipped at its edge."""
    pad_x, pad_y = p(80), p(40)
    surf = pygame.Surface((w + 2 * pad_x, h + 2 * pad_y), pygame.SRCALPHA)
    n = 12 + w // p(40)
    for i in range(n):
        u = i / max(1, n - 1)
        cx = pad_x + int(w * u + rng.uniform(-p(12), p(12)))
        cy = pad_y + int(h * (0.62 - 0.25 * math.sin(u * math.pi)) + rng.uniform(-p(6), p(6)))
        rx = int(p(rng.randint(34, 62)) * (0.55 + 0.6 * math.sin(u * math.pi)))
        ry = int(rx * rng.uniform(0.38, 0.55))
        blob = make_blob(rx, ry, CLOUD_COLOR, rng.randint(120, 175), 1.4)
        surf.blit(blob, blob.get_rect(center=(cx, cy)))
    return surf


def build_fog_layer(w: int, h: int, p, rng: random.Random, density: float) -> pygame.Surface:
    """Wrap-seamless fog bank: every blob is also drawn at x +/- w."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    n = int(44 * density)
    for _ in range(n):
        rx = p(rng.randint(45, 120))
        ry = p(rng.randint(12, 32))
        cx = rng.randint(0, w)
        cy = int(h * (0.55 + 0.45 * rng.random() ** 0.7))
        blob = make_blob(rx, ry, FOG_COLOR, rng.randint(34, 58), 1.5)
        for off in (-w, 0, w):
            surf.blit(blob, blob.get_rect(center=(cx + off, cy)))
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h - 1)
        a = int(255 * clamp(t / 0.55, 0.0, 1.0) * (1.0 - 0.25 * max(0.0, t - 0.75) / 0.25))
        grad.fill((255, 255, 255, a), (0, y, w, 1))
    surf.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surf


# ------------------------------------------------------------ dynamic actors

class Bat:
    __slots__ = ("x", "y", "vx", "bob_amp", "bob_rate", "bob_phase", "flap_rate", "flap_phase",
                 "size")

    def __init__(self, x, y, vx, bob_amp, bob_rate, bob_phase, flap_rate, size) -> None:
        self.x, self.y, self.vx = x, y, vx
        self.bob_amp, self.bob_rate, self.bob_phase = bob_amp, bob_rate, bob_phase
        self.flap_rate, self.flap_phase, self.size = flap_rate, 0.0, size


class Spider:
    """Drops from the top-right web on a thread, wanders the rack face, climbs back."""

    def __init__(self, anchor: tuple[int, int], face: pygame.Rect, rs: float,
                 rng: random.Random) -> None:
        self.anchor = anchor
        self.face = face
        self.rs = rs
        self.rng = rng
        self.state = "home"
        self.x, self.y = float(anchor[0]), float(anchor[1])
        self.target_y = 0.0
        self.dir = 1
        self.walk_left = 0.0
        self.pause = 0.0
        self.leg_phase = 0.0

    def start(self) -> None:
        if self.state != "home":
            return
        self.state = "descend"
        self.x, self.y = float(self.anchor[0]), float(self.anchor[1])
        self.target_y = self.rng.uniform(self.face.top + self.face.height * 0.2,
                                         self.face.bottom - self.face.height * 0.1)
        self.walk_left = self.rng.uniform(0.5, 1.4) * self.face.width
        self.dir = -1 if self.rng.random() < 0.7 else 1

    def update(self, dt: float) -> None:
        rs = self.rs
        if self.state == "descend":
            self.y += SPIDER_DESCEND_SPEED * rs * dt
            self.leg_phase += dt * 3.0
            if self.y >= self.target_y:
                self.y = self.target_y
                self.state = "walk"
        elif self.state == "walk":
            if self.pause > 0:
                self.pause -= dt
                return
            step = SPIDER_WALK_SPEED * rs * dt
            self.x += self.dir * step
            self.y += math.sin(self.leg_phase * 0.5) * 0.15 * rs
            self.leg_phase += dt * 11.0
            self.walk_left -= step
            margin = 8 * rs
            if self.x < self.face.left + margin or self.x > self.face.right - margin:
                self.dir = -self.dir
            if self.rng.random() < dt * 0.35:
                self.pause = self.rng.uniform(0.4, 1.6)
            if self.walk_left <= 0:
                self.state = "ascend"
        elif self.state == "ascend":
            dy = SPIDER_CLIMB_SPEED * rs * dt
            self.y -= dy
            self.leg_phase += dt * 7.0
            total = max(1.0, self.y - self.anchor[1])
            self.x += (self.anchor[0] - self.x) * clamp(dy / total, 0.0, 1.0)
            if self.y <= self.anchor[1] + 2 * rs:
                self.state = "home"

    def draw(self, s: pygame.Surface) -> None:
        if self.state == "home":
            return
        rs = self.rs
        x, y = self.x, self.y
        pygame.draw.line(s, (176, 176, 190), self.anchor, (x, y - 7 * rs))
        lw = 1 if rs < 0.8 else 2
        for i in range(4):
            a = math.radians((-62, -28, 14, 48)[i])
            swing = math.sin(self.leg_phase + i * math.pi / 2) * 2.2 * rs
            for side in (-1, 1):
                sw = swing * side * (1 if i % 2 == 0 else -1)
                kx = x + side * (math.cos(a) * 8 * rs + sw * 0.5)
                ky = y + math.sin(a) * 6 * rs - 4 * rs
                fx = kx + side * (6 * rs + sw)
                fy = ky + 9 * rs + abs(math.sin(a)) * 2 * rs
                pygame.draw.lines(s, SPIDER_COLOR, False, [(x, y), (kx, ky), (fx, fy)], lw)
        ab = pygame.Rect(0, 0, max(3, int(9 * rs)), max(4, int(11 * rs)))
        ab.center = (int(x), int(y + 2 * rs))
        pygame.draw.ellipse(s, SPIDER_COLOR, ab)
        pygame.draw.ellipse(s, (52, 46, 56), ab, 1)
        pygame.draw.circle(s, SPIDER_COLOR, (int(x), int(y - 5 * rs)), max(2, int(4 * rs)))
        for side in (-1, 1):
            s.fill(SPIDER_EYES, (int(x + side * 1.6 * rs - 0.5), int(y - 6 * rs), 1, 1))


# ------------------------------------------------------------------ the app

class Halloween26:
    def __init__(self, fullscreen: bool, fps_cap: int, dev: bool, win_scale: float,
                 speed: float, detail: str, render_scale: float, seed: int | None,
                 max_frames: int, fog: bool, bats: bool, spider: bool,
                 bat_interval: tuple[float, float], spider_interval: tuple[float, float],
                 rare_interval: tuple[float, float], screenshot: str | None,
                 tombstone_text: tuple[str, ...] = TOMBSTONE_LINES,
                 screen_text: str = SCREEN_TEXT) -> None:
        pygame.init()
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.speed = max(0.05, speed)
        self.max_frames = max_frames
        self.fog_enabled = fog
        self.bats_enabled = bats
        self.spider_enabled = spider
        self.bat_interval = bat_interval
        self.spider_interval = spider_interval
        self.rare_interval = rare_interval
        self.screenshot = screenshot
        self.tombstone_text = tuple(tombstone_text)
        self.screen_text = screen_text.strip()
        preset = DETAIL_PRESETS[detail]
        self.preset = preset
        self.smooth = bool(preset["smooth"])

        rs = clamp(render_scale, 0.3, 1.0)
        self.rs = rs
        self.rw = max(1, int(SCREEN_W * rs))
        self.rh = max(1, int(SCREEN_H * rs))

        if dev:
            win = (max(1, int(SCREEN_W * win_scale)), max(1, int(SCREEN_H * win_scale)))
            self.screen = pygame.display.set_mode(win, pygame.RESIZABLE)
            pygame.display.set_caption("Halloween 2026 (dev - Esc to quit)")
        else:
            flags = pygame.NOFRAME
            if fullscreen:
                flags |= pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
            pygame.display.set_caption("Halloween 2026")

        if self.screen.get_size() == (self.rw, self.rh):
            self.frame = self.screen
        else:
            self.frame = pygame.Surface((self.rw, self.rh))

        self.clock = pygame.time.Clock()
        self.fps_cap = fps_cap
        self.running = True
        self.t = 0.0

        self.font_path = optional_asset("tombstone.ttf")
        self._build_scene()

        self.flock_timer = self.rng.uniform(2.0, 6.0)
        self.spider_timer = self.rng.uniform(4.0, 12.0)
        self.rare_timer = self.rng.uniform(*rare_interval) * 0.5
        self.shimmer_timer = self.rng.uniform(1.0, 4.0)
        self.shimmer_t = -1.0
        self.bats: list[Bat] = []
        self.effects: list[dict] = []
        self.panic_t = -1.0

    # ---------------------------------------------------------------- helpers

    def S(self, v: float) -> int:
        return int(round(v * self.rs))

    def P(self, v: float) -> int:
        return max(1, int(round(v * self.rs)))

    def _make_font(self, size: int) -> pygame.font.Font:
        size = max(8, size)
        if self.font_path is not None:
            try:
                return pygame.font.Font(str(self.font_path), size)
            except (pygame.error, OSError):
                pass
        try:
            return pygame.font.SysFont(
                "chiller,oldenglishtextmt,blackadderitc,dejavuserif,liberationserif,serif",
                size, bold=True)
        except (pygame.error, OSError):
            return pygame.font.Font(None, size)

    # ------------------------------------------------------------ scene build

    def _build_scene(self) -> None:
        S, P, rs, rng = self.S, self.P, self.rs, self.rng
        w, h = self.rw, self.rh
        bg = pygame.Surface((w, h))
        hor = S(HORIZON_Y)

        # Sky gradient.
        for y in range(h):
            t = min(1.0, y / max(1, hor))
            if t < 0.55:
                c = lerp_color(SKY_TOP, SKY_MID, t / 0.55)
            else:
                c = lerp_color(SKY_MID, SKY_HORIZON, (t - 0.55) / 0.45)
            bg.fill(c, (0, y, w, 1))

        # Stars (static) and twinklers (animated later).
        mx, my, mr = S(MOON_POS[0]), S(MOON_POS[1]), S(MOON_RADIUS)
        stars = 0
        while stars < int(150 * rs):
            x, y = rng.randint(0, w - 1), rng.randint(0, hor - S(30))
            if math.hypot(x - mx, y - my) < mr * 1.5:
                continue
            k = rng.random() ** 2
            bg.set_at((x, y), lerp_color((60, 60, 80), STAR_COLOR, k))
            if k > 0.85 and rs >= 0.7:
                bg.set_at((x + 1, y), (90, 90, 110))
            stars += 1
        self.twinklers = []
        for _ in range(int(self.preset["twinklers"])):
            while True:
                x, y = rng.randint(2, w - 3), rng.randint(2, hor - S(40))
                if math.hypot(x - mx, y - my) >= mr * 1.6:
                    break
            self.twinklers.append((x, y, rng.uniform(0.6, 2.2), rng.uniform(0, math.tau),
                                   1 if rng.random() < 0.7 else 2))

        # Moon with additive halo.
        halo = make_glow_rgb(int(mr * 2.7), int(mr * 2.7), MOON_HALO, 2.4)
        bg.blit(halo, halo.get_rect(center=(mx, my)), special_flags=pygame.BLEND_RGB_ADD)
        halo2 = make_glow_rgb(int(mr * 1.4), int(mr * 1.4), (110, 92, 50), 1.5)
        bg.blit(halo2, halo2.get_rect(center=(mx, my)), special_flags=pygame.BLEND_RGB_ADD)
        moon_img = load_optional_image("moon.png")
        if moon_img is not None:
            moon = pygame.transform.smoothscale(moon_img, (mr * 2, mr * 2))
        else:
            moon = build_moon(mr, random.Random(self.seed ^ 0x5EED))
        bg.blit(moon, moon.get_rect(center=(mx, my)))

        # Horizon haze.
        haze = pygame.Surface((w, S(70)), pygame.SRCALPHA)
        for y in range(haze.get_height()):
            a = int(90 * (y / haze.get_height()) ** 2)
            haze.fill((*HAZE_COLOR, a), (0, y, w, 1))
        bg.blit(haze, (0, hor - haze.get_height()))

        # Far hills with distant grave markers, then the trees, then near hills.
        offs = [rng.uniform(0, math.tau) for _ in range(3)]
        far_pts = [(x, hill_y(x, w, hor - S(16), S(18), offs)) for x in range(0, w + 4, 4)]
        pygame.draw.polygon(bg, HILL_FAR, far_pts + [(w, h), (0, h)])
        for _ in range(5):
            gx = rng.randint(S(20), w - S(20))
            if abs(gx - S(RACK_RECT[0] + RACK_RECT[2] / 2)) < S(140):
                continue
            gy = int(hill_y(gx, w, hor - S(16), S(18), offs))
            gw, gh = P(rng.randint(6, 10)), P(rng.randint(9, 15))
            if rng.random() < 0.6:
                pygame.draw.rect(bg, HILL_FAR, (gx - gw // 2, gy - gh, gw, gh + 2),
                                 border_top_left_radius=gw // 2, border_top_right_radius=gw // 2)
            else:
                bg.fill(HILL_FAR, (gx - P(1), gy - gh, P(2), gh + 2))
                bg.fill(HILL_FAR, (gx - gw // 2, gy - gh + P(3), gw, P(2)))
        tree_rng = random.Random(self.seed ^ 0x7EE)
        draw_tree(bg, S(TREE_LEFT[0]), S(TREE_LEFT[1]), S(TREE_LEFT[2]), tree_rng)
        draw_tree(bg, S(TREE_RIGHT[0]), S(TREE_RIGHT[1]), S(TREE_RIGHT[2]), tree_rng)
        self.owl_pos = (S(TREE_LEFT[0] + OWL_OFFSET[0]), S(TREE_LEFT[1] + OWL_OFFSET[1]))
        offs2 = [rng.uniform(0, math.tau) for _ in range(3)]
        near_pts = [(x, hill_y(x, w, hor - S(3), S(7), offs2)) for x in range(0, w + 4, 4)]
        pygame.draw.polygon(bg, HILL_NEAR, near_pts + [(w, h), (0, h)])

        # Ground plane with speckle and grass tufts.
        gy0 = S(GROUND_Y)
        for y in range(gy0, h):
            t = (y - gy0) / max(1, h - gy0)
            bg.fill(lerp_color(GROUND_TOP, GROUND_BOT, t ** 0.8), (0, y, w, 1))
        for _ in range(int(700 * rs)):
            x, y = rng.randint(0, w - 1), rng.randint(gy0, h - 1)
            c = bg.get_at((x, y))
            bg.set_at((x, y), lerp_color(c[:3], rng.choice(((40, 36, 34), (4, 4, 6))), 0.6))
        for _ in range(int(360 * rs)):
            x = rng.randint(0, w - 1)
            y = gy0 + int((h - gy0) * rng.random() ** 1.8)
            ln = P(rng.randint(3, 8))
            pygame.draw.line(bg, rng.choice(GRASS_COLORS), (x, y),
                             (x + rng.randint(-2, 2), y - ln))

        # Server rack and its cobwebs.
        rx, ry, rw_, rh_ = (S(v) for v in RACK_RECT)
        self.rack_pos = (rx, ry)
        rack, leds, screen = build_rack(rw_, rh_, P, rng, self._make_font, self.screen_text)
        bg.blit(rack, (rx, ry))
        if screen is not None:
            screen["pos"] = (rx + screen["pos"][0], ry + screen["pos"][1])
        self.rack_screen = screen
        for i, led in enumerate(leds):
            led.x += rx
            led.y += ry
            led.idx = i
        self.leds = leds
        self.rack_face = pygame.Rect(rx + S(14), ry + S(10), rw_ - S(28), rh_ - S(24))
        web_rng = random.Random(self.seed ^ 0x3EB)
        draw_cobweb(bg, rx + S(9), ry + S(8), S(36), 0.0, math.pi / 2, web_rng)
        draw_cobweb(bg, rx + rw_ - S(9), ry + S(8), S(30), math.pi / 2, math.pi, web_rng)
        draw_cobweb(bg, rx, ry + rh_ - S(2), S(50), math.pi, math.pi * 1.5, web_rng)
        self.spider = Spider((rx + rw_ - S(16), ry + S(9)), self.rack_face, rs, rng)

        # Tombstones: mound, small back stone, main stone.
        tcx, tby, tw, th = (S(v) for v in TOMBSTONE)
        mound = pygame.Surface((int(tw * 1.7), S(22)), pygame.SRCALPHA)
        pygame.draw.ellipse(mound, (26, 22, 20, 255), mound.get_rect())
        bg.blit(mound, mound.get_rect(center=(tcx, tby - S(2))))
        bcx, bby, bw, bh, btilt = BACK_STONE
        back = build_small_stone(S(bw), S(bh), btilt, P, rng)
        bg.blit(back, back.get_rect(midbottom=(S(bcx), S(bby))))
        plinth = pygame.Rect(0, 0, tw + S(10), S(10))
        plinth.midbottom = (tcx, tby)
        pygame.draw.rect(bg, (54, 56, 62), plinth)
        bg.fill((76, 78, 86), (plinth.x, plinth.y, plinth.width, P(1)))
        stone, frames = build_tombstone(tw, th, P, rng, self._make_font,
                                        load_optional_image("tombstone.png"),
                                        self.tombstone_text)
        self.stone_rect = stone.get_rect(midbottom=(tcx + S(3), tby - S(6)))
        bg.blit(stone, self.stone_rect.topleft)
        self.shimmer_frames = frames
        self.shimmer_idle = frames[len(frames) // 2]

        # Pumpkins.
        self.pumpkins = []
        for cx, by, pw, face_id in PUMPKINS:
            body, face, levels, (ox, oy, bw_, bh_) = build_pumpkin(S(pw), face_id, P, rng)
            pos = (S(cx) - ox - bw_ // 2, S(by) - oy - bh_)
            bg.blit(body, pos)
            self.pumpkins.append({
                "pos": pos, "face": face, "levels": levels,
                "glow_center": (S(cx), S(by) - bh_ // 3),
                "f1": rng.uniform(5.0, 9.0), "f2": rng.uniform(11.0, 17.0),
                "p1": rng.uniform(0, math.tau), "p2": rng.uniform(0, math.tau),
                "jit": 0.0, "gutter": 0.0,
            })

        # Vignette baked into the background (edges and top).
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        ew = S(150)
        for x in range(ew):
            a = int(120 * (1 - x / ew) ** 2.2)
            vig.fill((0, 0, 0, a), (x, 0, 1, h))
            vig.fill((0, 0, 0, a), (w - 1 - x, 0, 1, h))
        for y in range(S(50)):
            a = int(70 * (1 - y / S(50)) ** 2)
            vig.fill((0, 0, 0, a), (0, y, w, 1))
        bg.blit(vig, (0, 0))
        self.bg = bg

        # Dynamic sprites.
        self.clouds = []
        for _ in range(int(self.preset["clouds"])):
            cw = S(rng.randint(280, 440))
            ch = S(rng.randint(60, 95))
            self.clouds.append({
                "sprite": build_cloud(cw, ch, P, rng),
                "x": rng.uniform(-cw, w), "y": rng.uniform(S(10), S(120)),
                "speed": WIND_SPEED * rs * rng.uniform(0.7, 1.3),
            })
        self.fog_layers = []
        n_fog = int(self.preset["fog_layers"])
        for i in range(n_fog):
            depth = i / max(1, n_fog - 1)          # 0 = far/thin, 1 = near/thick
            lw = w + S(300)
            lh = S(70 + 50 * depth)
            self.fog_layers.append({
                "sprite": build_fog_layer(lw, lh, P, rng, 0.7 + 0.6 * depth),
                "w": lw, "y": h - lh, "x": rng.uniform(0, lw),
                "speed": WIND_SPEED * rs * (0.6 + 1.3 * depth) * rng.choice((1.0, -0.8)),
                "base_alpha": 140 + 70 * depth,
                "period": rng.uniform(*FOG_PERIOD), "phase": rng.uniform(0, math.tau),
            })
        self.bat_frames = [build_bat_frames(S(size), P) for size in (18, 28, 40)]
        self.fireflies = []
        for _ in range(int(self.preset["fireflies"])):
            self.fireflies.append({
                "x": rng.uniform(0, w), "y": rng.uniform(S(200), S(308)),
                "rate": rng.uniform(0.4, 1.3), "phase": rng.uniform(0, math.tau),
                "drift": rng.uniform(0, math.tau),
            })
        self.wisp_sprite = make_blob(S(22), S(48), WISP_COLOR, 120, 1.8)
        self.flash_bolt: list[tuple[float, float]] | None = None

    # ------------------------------------------------------------- spawning

    def _spawn_flock(self) -> None:
        rng, rs = self.rng, self.rs
        lo, hi = self.preset["flock"]
        n = rng.randint(lo, hi)
        side = rng.choice((-1, 1))
        speed = rng.uniform(*BAT_SPEED) * rs
        y0 = rng.uniform(self.S(30), self.S(175))
        x0 = -self.S(60) if side > 0 else self.rw + self.S(60)
        for i in range(n):
            size = rng.choices((0, 1, 2), weights=(3, 5, 2))[0]
            self.bats.append(Bat(
                x=x0 - side * i * rng.uniform(16, 42) * rs,
                y=y0 + rng.gauss(0, 20) * rs,
                vx=side * speed * rng.uniform(0.85, 1.15),
                bob_amp=rng.uniform(4, 12) * rs, bob_rate=rng.uniform(1.2, 2.6),
                bob_phase=rng.uniform(0, math.tau), flap_rate=rng.uniform(*BAT_FLAP_HZ),
                size=size,
            ))

    def _spawn_rare(self) -> None:
        kind = self.rng.choices(
            ("lightning", "panic", "wisp", "shooting_star", "owl"),
            weights=(3, 2, 3, 3, 2))[0]
        if kind == "panic":
            self.panic_t = 0.0
            return
        fx: dict = {"kind": kind, "t": 0.0}
        if kind == "lightning":
            fx["dur"] = 0.9
            fx["flashes"] = ((0.0, 0.08, 1.0), (0.14, 0.05, 0.5), (0.3, 0.1, 0.8))
            x = self.rng.uniform(self.rw * 0.05, self.rw * 0.45)
            pts = [(x, 0.0)]
            y = 0.0
            while y < self.S(HORIZON_Y - 20):
                y += self.rng.uniform(10, 26) * self.rs
                x += self.rng.uniform(-18, 18) * self.rs
                pts.append((x, y))
            fx["bolt"] = pts
        elif kind == "wisp":
            fx["dur"] = 8.0
            fx["x0"] = self.stone_rect.centerx - self.S(10)
        elif kind == "shooting_star":
            fx["dur"] = 0.75
            fx["x"] = self.rng.uniform(self.rw * 0.1, self.rw * 0.7)
            fx["y"] = self.rng.uniform(self.S(10), self.S(70))
            fx["vx"] = self.rng.uniform(700, 1000) * self.rs * self.rng.choice((-1, 1))
            fx["vy"] = self.rng.uniform(140, 260) * self.rs
        else:
            fx["dur"] = 4.6
        self.effects.append(fx)

    # ---------------------------------------------------------------- update

    def update(self, dt: float) -> None:
        dt *= self.speed
        self.t += dt
        rng = self.rng

        if self.bats_enabled:
            self.flock_timer -= dt
            if self.flock_timer <= 0:
                self._spawn_flock()
                self.flock_timer = rng.uniform(*self.bat_interval)
            keep = []
            for b in self.bats:
                b.x += b.vx * dt
                b.flap_phase += b.flap_rate * dt
                if -self.S(80) < b.x < self.rw + self.S(80):
                    keep.append(b)
            self.bats = keep

        if self.spider_enabled:
            self.spider_timer -= dt
            if self.spider_timer <= 0 and self.spider.state == "home":
                self.spider.start()
                self.spider_timer = rng.uniform(*self.spider_interval)
            self.spider.update(dt)

        self.rare_timer -= dt
        if self.rare_timer <= 0:
            self._spawn_rare()
            self.rare_timer = rng.uniform(*self.rare_interval)
        for fx in self.effects:
            fx["t"] += dt
        self.effects = [fx for fx in self.effects if fx["t"] < fx["dur"]]
        if self.panic_t >= 0:
            self.panic_t += dt
            if self.panic_t > 9.5:
                self.panic_t = -1.0

        if self.shimmer_t >= 0:
            self.shimmer_t += dt
            if self.shimmer_t >= SHIMMER_DURATION:
                self.shimmer_t = -1.0
                self.shimmer_timer = rng.uniform(*SHIMMER_INTERVAL)
        else:
            self.shimmer_timer -= dt
            if self.shimmer_timer <= 0:
                self.shimmer_t = 0.0

        for c in self.clouds:
            c["x"] += c["speed"] * dt
            cw = c["sprite"].get_width()
            if c["x"] > self.rw + 10:
                c["x"] = -cw - rng.uniform(0, self.rw * 0.5)
                c["y"] = rng.uniform(self.S(10), self.S(120))
        for f in self.fog_layers:
            f["x"] = (f["x"] + f["speed"] * dt) % f["w"]

        k = min(1.0, dt * 14.0)
        for p in self.pumpkins:
            p["jit"] += (rng.uniform(-1.0, 1.0) - p["jit"]) * k
            if p["gutter"] > 0:
                p["gutter"] -= dt
            elif rng.random() < dt * 0.04:
                p["gutter"] = rng.uniform(0.3, 0.8)

        for ff in self.fireflies:
            ff["x"] += math.sin(self.t * 0.6 + ff["drift"]) * 9 * self.rs * dt
            ff["y"] += math.cos(self.t * 0.45 + ff["drift"] * 1.7) * 6 * self.rs * dt
            ff["x"] %= self.rw
            ff["y"] = clamp(ff["y"], self.S(190), self.S(312))

    # ------------------------------------------------------------------ draw

    def _led_on(self, led: Led) -> tuple[int, int, int] | None:
        t = self.t
        if self.panic_t >= 0:
            pt = self.panic_t
            if pt < 3.0:
                return LED_RED if (pt * 3.0) % 1.0 < 0.5 else None
            if pt < 5.0:
                return None
            return LED_GREEN if (pt - 5.0) > 4.0 * led.idx / max(1, len(self.leds)) else None
        kind = led.kind
        if kind == "power":
            return led.color
        if kind == "act":
            v = math.sin(t * led.rate + led.phase) + math.sin(t * led.rate * 2.7 + led.phase * 3)
            return led.color if v > 0.3 else None
        if kind == "net":
            return led.color if ((t * led.rate + led.phase) % 1.0) < 0.5 else None
        if kind == "hdd":
            return led.color if ((t * led.rate + led.phase) % 1.0) < 0.14 else None
        return led.color if ((t * led.rate + led.phase) % 1.0) < 0.5 else None

    def _draw_leds(self, s: pygame.Surface) -> None:
        for led in self.leds:
            col = self._led_on(led)
            if col is None:
                continue
            s.fill(scale_color(col, 0.35), (led.x - 1, led.y - 1, led.w + 2, led.h + 2))
            s.fill(col, (led.x, led.y, led.w, led.h))

    def _draw_screen(self, s: pygame.Surface) -> None:
        """Mock Waveshare panel text: slow brightness pulse with a rare flicker dip."""
        if self.rack_screen is None:
            return
        t = self.t
        level = 0.86 + 0.14 * math.sin(t * 1.7)
        if math.sin(t * 23.0) * math.sin(t * 0.37) > 0.985:
            level *= 0.55
        content = self.rack_screen["content"]
        content.set_alpha(int(255 * level))
        s.blit(content, self.rack_screen["pos"])

    def _draw_pumpkins(self, s: pygame.Surface) -> None:
        t = self.t
        for p in self.pumpkins:
            flick = (0.74 + 0.16 * math.sin(t * p["f1"] + p["p1"])
                     + 0.08 * math.sin(t * p["f2"] + p["p2"]) + 0.06 * p["jit"])
            if p["gutter"] > 0:
                flick *= 0.45
            flick = clamp(flick, 0.25, 1.0)
            glow = p["levels"][min(GLOW_LEVELS - 1, int(flick * GLOW_LEVELS))]
            s.blit(glow, glow.get_rect(center=p["glow_center"]), special_flags=pygame.BLEND_RGB_ADD)
            face = p["face"]
            face.set_alpha(int(255 * flick))
            s.blit(face, p["pos"])

    def _draw_bats(self, s: pygame.Surface) -> None:
        for b in self.bats:
            frames = self.bat_frames[b.size]
            frame = frames[FLAP_SEQUENCE[int(b.flap_phase * 6) % 6]]
            y = b.y + math.sin(self.t * b.bob_rate + b.bob_phase) * b.bob_amp
            s.blit(frame, frame.get_rect(center=(int(b.x), int(y))))

    def _draw_effects(self, s: pygame.Surface) -> None:
        for fx in self.effects:
            kind, t = fx["kind"], fx["t"]
            if kind == "wisp":
                prog = t / fx["dur"]
                a = int(160 * math.sin(prog * math.pi))
                x = fx["x0"] + math.sin(t * 1.3) * self.S(14)
                y = self.stone_rect.centery - prog * self.S(110)
                self.wisp_sprite.set_alpha(a)
                s.blit(self.wisp_sprite, self.wisp_sprite.get_rect(center=(int(x), int(y))))
            elif kind == "shooting_star":
                prog = t / fx["dur"]
                x = fx["x"] + fx["vx"] * t
                y = fx["y"] + fx["vy"] * t
                tail = self.S(70) * (1 - prog * 0.5)
                mag = math.hypot(fx["vx"], fx["vy"])
                tx, ty = x - fx["vx"] / mag * tail, y - fx["vy"] / mag * tail
                fade = 1.0 - prog
                pygame.draw.line(s, scale_color((110, 110, 170), fade), (tx, ty), (x, y), self.P(3))
                pygame.draw.line(s, scale_color((235, 235, 255), fade),
                                 ((x + tx) / 2, (y + ty) / 2), (x, y), self.P(2))
                pygame.draw.circle(s, scale_color((255, 255, 255), fade), (int(x), int(y)),
                                   self.P(2))
            elif kind == "owl":
                closed = any(a <= t < b for a, b in ((1.4, 1.55), (3.0, 3.15), (3.3, 3.45)))
                if not closed:
                    ox, oy = self.owl_pos
                    r = self.P(3)
                    for side in (-1, 1):
                        cx = ox + side * self.S(5)
                        pygame.draw.circle(s, (230, 200, 60), (cx, oy), r)
                        s.fill((20, 10, 10), (cx, oy - r + 1, 1, 2 * r - 1))
            elif kind == "lightning":
                for start, dur, inten in fx["flashes"]:
                    if start <= t < start + dur:
                        a = int(70 * inten)
                        s.fill((a, a, a + 18), special_flags=pygame.BLEND_RGB_ADD)
                        if start == 0.0 or inten > 0.7:
                            pygame.draw.lines(s, (150, 140, 220), False, fx["bolt"], self.P(4))
                            pygame.draw.lines(s, (240, 240, 255), False, fx["bolt"], self.P(2))
                        break

    def draw(self) -> None:
        s = self.frame
        s.blit(self.bg, (0, 0))
        t = self.t

        for x, y, rate, phase, size in self.twinklers:
            k = 0.5 + 0.5 * math.sin(t * rate + phase)
            s.fill(lerp_color((50, 50, 70), STAR_COLOR, k * k), (x, y, size, size))

        for c in self.clouds:
            s.blit(c["sprite"], (int(c["x"]), int(c["y"])))

        self._draw_leds(s)
        self._draw_screen(s)
        if self.spider_enabled:
            self.spider.draw(s)

        # Tombstone lettering: faint constant pulse plus a periodic moonlight sweep.
        self.shimmer_idle.set_alpha(int(8 + 7 * math.sin(t * 0.8)))
        s.blit(self.shimmer_idle, self.stone_rect.topleft)
        if self.shimmer_t >= 0:
            prog = self.shimmer_t / SHIMMER_DURATION
            frame = self.shimmer_frames[min(SHIMMER_FRAMES - 1, int(prog * SHIMMER_FRAMES))]
            frame.set_alpha(int(95 * math.sin(prog * math.pi)))
            s.blit(frame, self.stone_rect.topleft)

        self._draw_pumpkins(s)

        for ff in self.fireflies:
            k = max(0.0, math.sin(t * ff["rate"] + ff["phase"])) ** 3
            if k > 0.02:
                s.fill(scale_color(FIREFLY_COLOR, k),
                       (int(ff["x"]), int(ff["y"]), self.P(2), self.P(2)),
                       special_flags=pygame.BLEND_RGB_ADD)

        self._draw_effects(s)

        if self.fog_enabled:
            for f in self.fog_layers:
                wave = max(0.0, math.sin(math.tau * t / f["period"] + f["phase"]))
                env = 0.12 + 0.88 * wave ** 2.2
                f["sprite"].set_alpha(int(f["base_alpha"] * env))
                x = int(f["x"])
                s.blit(f["sprite"], (x - f["w"], f["y"]))
                s.blit(f["sprite"], (x, f["y"]))

        if self.bats_enabled:
            self._draw_bats(s)

        if s is not self.screen:
            if self.smooth and self.rs >= 0.85:
                self.screen.blit(pygame.transform.smoothscale(s, self.screen.get_size()), (0, 0))
            else:
                pygame.transform.scale(s, self.screen.get_size(), self.screen)
        pygame.display.flip()

    # ------------------------------------------------------------------ loop

    def run(self) -> None:
        frames = 0
        elapsed = 0.0
        while self.running:
            dt = self.clock.tick(self.fps_cap) / 1000.0
            if dt > 0.1:
                dt = 0.1
            elapsed += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.running = False

            self.update(dt)
            self.draw()

            frames += 1
            if self.max_frames and frames >= self.max_frames:
                self.running = False

        if self.screenshot:
            pygame.image.save(self.frame, self.screenshot)
            print(f"Saved {self.screenshot}")
        if self.max_frames and elapsed > 0:
            print(f"Rendered {frames} frames in {elapsed:.2f}s "
                  f"({frames / elapsed:.1f} fps average)")
        pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Halloween 2026 DSI screensaver (1480x320)")
    parser.add_argument("--dev", action="store_true",
                        help="Development mode: resizable scaled preview (Esc to quit)")
    parser.add_argument("--scale", type=float, default=0.65,
                        help="Window scale in --dev mode (default: 0.65)")
    parser.add_argument("--fullscreen", action="store_true",
                        help="Fullscreen borderless (recommended on Raspberry Pi)")
    parser.add_argument("--fps", type=int, default=60,
                        help="Frame rate cap (default: 60; try 30 on a Pi)")
    parser.add_argument("--speed", type=float, default=ANIM_SPEED,
                        help=f"Animation speed multiplier (default: {ANIM_SPEED:g})")
    parser.add_argument("--detail", choices=sorted(DETAIL_PRESETS), default="medium",
                        help="Detail preset: low / medium / high (default: medium)")
    parser.add_argument("--render-scale", type=float, default=1.0,
                        help="Internal render resolution, 0.3..1.0 "
                             "(0.5 roughly quadruples FPS on a Pi; default: 1.0)")
    parser.add_argument("--bat-interval", type=float, nargs=2, metavar=("MIN", "MAX"),
                        default=list(BAT_INTERVAL),
                        help="Seconds between bat flocks "
                             f"(default: {BAT_INTERVAL[0]:g} {BAT_INTERVAL[1]:g})")
    parser.add_argument("--spider-interval", type=float, nargs=2, metavar=("MIN", "MAX"),
                        default=list(SPIDER_INTERVAL),
                        help="Seconds between spider crawls "
                             f"(default: {SPIDER_INTERVAL[0]:g} {SPIDER_INTERVAL[1]:g})")
    parser.add_argument("--rare-interval", type=float, nargs=2, metavar=("MIN", "MAX"),
                        default=list(RARE_INTERVAL),
                        help="Seconds between rare events: lightning, kernel panic, wisp, "
                             f"shooting star, owl (default: {RARE_INTERVAL[0]:g} "
                             f"{RARE_INTERVAL[1]:g})")
    parser.add_argument("--no-fog", dest="fog", action="store_false",
                        help="Disable the drifting ground fog")
    parser.add_argument("--no-bats", dest="bats", action="store_false",
                        help="Disable bat flocks")
    parser.add_argument("--no-spider", dest="spider", action="store_false",
                        help="Disable the rack spider")
    parser.add_argument("--tombstone-text", nargs="+", metavar="LINE",
                        default=list(TOMBSTONE_LINES),
                        help="Lines engraved on the tombstone, one argument per line "
                             f"(default: {' '.join(repr(ln) for ln in TOMBSTONE_LINES)})")
    parser.add_argument("--screen-text", default=SCREEN_TEXT,
                        help="Text shown on the mock Waveshare screen in the rack "
                             f"(default: {SCREEN_TEXT!r})")
    parser.add_argument("--no-screen", dest="screen", action="store_false",
                        help="Remove the mock Waveshare screen from the rack")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for a repeatable scene layout")
    parser.add_argument("--frames", type=int, default=0,
                        help="Exit after N frames and print average FPS (benchmarking)")
    parser.add_argument("--screenshot", metavar="PATH", default=None,
                        help="Save the final 1480x320 frame to PATH on exit (use with --frames)")
    return parser.parse_args()


def main() -> int:
    verify_runtime()
    args = parse_args()
    Halloween26(
        fullscreen=args.fullscreen,
        fps_cap=args.fps,
        dev=args.dev,
        win_scale=args.scale if args.dev else 1.0,
        speed=args.speed,
        detail=args.detail,
        render_scale=args.render_scale,
        seed=args.seed,
        max_frames=args.frames,
        fog=args.fog,
        bats=args.bats,
        spider=args.spider,
        bat_interval=(min(args.bat_interval), max(args.bat_interval)),
        spider_interval=(min(args.spider_interval), max(args.spider_interval)),
        rare_interval=(min(args.rare_interval), max(args.rare_interval)),
        screenshot=args.screenshot,
        tombstone_text=tuple(args.tombstone_text),
        screen_text=args.screen_text if args.screen else "",
    ).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Generate a self-hosted 'tools I use' SVG.

Pulls each brand icon from simple-icons (CC0 1.0) on first run, caches them
under assets/icons/, then composes a single SVG with rounded brand-colored
tiles. After the first run there's no network dependency.

Run:
    python3 scripts/build_tools.py

Edit TOOLS below to add / reorder / remove tiles.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets"
ICONS_DIR = OUTPUT_DIR / "icons"
SOURCE_BASE = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons"

# (simple-icons slug, display label, tile background hex, icon fill hex or None=white)
TOOLS = [
    ("php",         "PHP",        "#777BB4", None),
    ("laravel",     "Laravel",    "#FF2D20", None),
    ("typescript",  "TypeScript", "#3178C6", None),
    ("go",          "Go",         "#00ADD8", None),
    ("rust",        "Rust",       "#1c1c1c", None),
    ("python",      "Python",     "#3776AB", None),
    ("react",       "React",      "#20232A", "#61DAFB"),
    ("tailwindcss", "Tailwind",   "#06B6D4", None),
    ("nodedotjs",   "Node.js",    "#5FA04E", None),
    ("docker",      "Docker",     "#2496ED", None),
    ("postgresql",  "PostgreSQL", "#4169E1", None),
    ("sqlite",      "SQLite",     "#003B57", None),
    ("godotengine", "Godot",      "#478CBF", None),
    ("linux",       "Linux",      "#1c1c1c", "#FCC624"),
    ("gnubash",     "Bash",       "#4EAA25", None),
    ("git",         "Git",        "#F05032", None),
]

PER_ROW = 4
BOX = 56
GAP = 12
MARGIN = 16
STAGGER = 0.05   # seconds between tile fade-ins
FADE_DUR = 0.45
WAVE_BASE = 2.5  # seconds before the first wave kicks in (after fade-ins)
WAVE_STEP = 0.10 # seconds between adjacent (diagonal) tiles in the wave
WAVE_CYCLE = 5.0 # full wave period (one pulse per tile per cycle)


def fetch_icon(slug: str) -> str:
    cache = ICONS_DIR / f"{slug}.svg"
    if cache.exists():
        return cache.read_text()
    url = f"{SOURCE_BASE}/{slug}.svg"
    print(f"  fetching {slug} from simple-icons …")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        raise SystemExit(f"failed to fetch {url}: {e}")
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(content)
    return content


def extract_path(svg: str, slug: str) -> str:
    m = re.search(r"<path\b[^>]*?/>", svg, flags=re.DOTALL)
    if not m:
        raise ValueError(f"no <path> found in icon for '{slug}'")
    path = m.group(0)
    # Strip any existing fill so the parent <svg fill="..."> wins.
    path = re.sub(r'\s+fill="[^"]*"', "", path)
    return path


def compose() -> str:
    rows = (len(TOOLS) + PER_ROW - 1) // PER_ROW
    width = MARGIN * 2 + PER_ROW * BOX + (PER_ROW - 1) * GAP
    height = MARGIN * 2 + rows * BOX + (rows - 1) * GAP

    inner = BOX - 16  # icon padding inside tile
    inner_offset = (BOX - inner) // 2

    tiles = []
    # Pulse occupies the first ~15% of each cycle so tiles spend most of the
    # time at rest. keyTimes match: 0 = at rest, 0.075 = peak lift, 0.15 = back
    # to rest, 1.0 = still at rest (loop).
    pulse_keytimes = "0;0.075;0.15;1"
    pulse_values = "0,0; 0,-4; 0,0; 0,0"

    for i, (slug, label, bg, icon_fill) in enumerate(TOOLS):
        col = i % PER_ROW
        row = i // PER_ROW
        x = MARGIN + col * (BOX + GAP)
        y = MARGIN + row * (BOX + GAP)
        path = extract_path(fetch_icon(slug), slug)
        fill = icon_fill or "#FFFFFF"
        fade_delay = i * STAGGER
        wave_delay = WAVE_BASE + (col + row) * WAVE_STEP
        tiles.append(
            f'  <g transform="translate({x}, {y})" opacity="0">'
            f'<title>{label}</title>'
            f'<rect width="{BOX}" height="{BOX}" rx="12" fill="{bg}"/>'
            f'<svg x="{inner_offset}" y="{inner_offset}" width="{inner}" '
            f'height="{inner}" viewBox="0 0 24 24" fill="{fill}">{path}</svg>'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{fade_delay:.2f}s" dur="{FADE_DUR}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'additive="sum" values="{pulse_values}" '
            f'keyTimes="{pulse_keytimes}" dur="{WAVE_CYCLE}s" '
            f'begin="{wave_delay:.2f}s" repeatCount="indefinite"/>'
            f'</g>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(tiles)
        + "\n</svg>\n"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    svg = compose()
    out = OUTPUT_DIR / "tools.svg"
    out.write_text(svg)
    print(f"Wrote {out} ({len(TOOLS)} tools)")


if __name__ == "__main__":
    main()

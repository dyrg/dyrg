#!/usr/bin/env python3
"""
Generate local stats and language SVGs for the GitHub profile README.

Walks every git repo under PROJECTS_DIR (default: ~/projects), counts commits
authored by the user's git email, and tallies lines of code per language by
file extension. Emits two theme-aware SVGs into assets/.

Run:
    python3 scripts/build_stats.py

Configure the scanned root or excluded repos via env vars (see CONFIG block).
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path

# --- CONFIG -----------------------------------------------------------------

PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", Path.home() / "projects"))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets"
SELF_REPO = "dyrg"  # this repo

# Directories never descended into when counting LOC.
EXCLUDE_DIRS = {
    ".git", "node_modules", "vendor", "target", "dist", "build", "out",
    ".next", ".turbo", ".cache", ".parcel-cache", ".nuxt", ".svelte-kit",
    "__pycache__", ".venv", "venv", "env", ".tox", ".pytest_cache",
    ".idea", ".vscode", "bower_components", "coverage",
    "public", "storage", "bootstrap", "sql",
}

# Substrings that, if present in a directory name, cause it to be skipped.
EXCLUDE_DIR_SUBSTRINGS = (
    "_bkp", "-bkp", ".bkp", "_backup", "_archive",
    "public_",
)

# Cap lines counted per file. Real source rarely exceeds this; vendored bundles
# and DB dumps routinely do. Acts as a safety net for the directory exclusions.
MAX_LINES_PER_FILE = 5000

# Top-level directories under PROJECTS_DIR that should not be scanned at all.
EXCLUDE_PROJECT_NAMES = {"traefik"}

# How deep to look for nested git repos.
SCAN_DEPTH = 3

# Files we never count (lockfiles, generated, minified).
EXCLUDE_FILE_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock",
    "Cargo.lock", "Gemfile.lock", "Pipfile.lock", "poetry.lock", "go.sum",
}
EXCLUDE_FILE_SUFFIXES = (".min.js", ".min.css", ".map", ".lock")

# Extension -> (canonical name, GitHub Linguist-ish color).
LANG_INFO: dict[str, tuple[str, str]] = {
    ".go":     ("Go",         "#00ADD8"),
    ".rs":     ("Rust",       "#dea584"),
    ".ts":     ("TypeScript", "#3178c6"),
    ".tsx":    ("TypeScript", "#3178c6"),
    ".js":     ("JavaScript", "#f1e05a"),
    ".jsx":    ("JavaScript", "#f1e05a"),
    ".mjs":    ("JavaScript", "#f1e05a"),
    ".cjs":    ("JavaScript", "#f1e05a"),
    ".py":     ("Python",     "#3572A5"),
    ".php":    ("PHP",        "#4F5D95"),
    ".rb":     ("Ruby",       "#701516"),
    ".java":   ("Java",       "#b07219"),
    ".kt":     ("Kotlin",     "#A97BFF"),
    ".swift":  ("Swift",      "#F05138"),
    ".c":      ("C",          "#555555"),
    ".h":      ("C",          "#555555"),
    ".cpp":    ("C++",        "#f34b7d"),
    ".cc":     ("C++",        "#f34b7d"),
    ".hpp":    ("C++",        "#f34b7d"),
    ".cs":     ("C#",         "#178600"),
    ".lua":    ("Lua",        "#000080"),
    ".sh":     ("Shell",      "#89e051"),
    ".bash":   ("Shell",      "#89e051"),
    ".zsh":    ("Shell",      "#89e051"),
    ".html":   ("HTML",       "#e34c26"),
    ".vue":    ("Vue",        "#41b883"),
    ".svelte": ("Svelte",     "#ff3e00"),
    ".css":    ("CSS",        "#563d7c"),
    ".scss":   ("SCSS",       "#c6538c"),
    ".sql":    ("SQL",        "#e38c00"),
}

# --- COLLECTION -------------------------------------------------------------

def git_email() -> str:
    out = subprocess.run(
        ["git", "config", "user.email"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return out or "you@example.com"


def is_repo(path: Path) -> bool:
    return path.is_dir() and (path / ".git").is_dir()


def find_repos(root: Path, max_depth: int = SCAN_DEPTH) -> list[Path]:
    """Walk up to max_depth levels under root, returning every git working tree.

    Once a directory contains .git, it counts as a repo and we don't descend
    into it (to avoid double-counting nested submodules).
    """
    if not root.is_dir():
        return []
    found: list[Path] = []

    def walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            name = entry.name
            if name == SELF_REPO and entry.parent == root:
                continue
            if entry.parent == root and name in EXCLUDE_PROJECT_NAMES:
                continue
            if excluded_dir(name):
                continue
            if is_repo(entry):
                found.append(entry)
                continue  # don't descend into a repo
            walk(entry, depth + 1)

    walk(root, 1)
    return found


def commits_for(repo: Path, email: str) -> tuple[int, set[str]]:
    """Return (commit_count, set of YYYY-MM-DD active dates) authored by email."""
    res = subprocess.run(
        ["git", "-C", str(repo), "log", f"--author={email}",
         "--pretty=tformat:%ad", "--date=short"],
        capture_output=True, text=True, check=False,
    )
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    return len(lines), set(lines)


def excluded_dir(name: str) -> bool:
    if name in EXCLUDE_DIRS:
        return True
    return any(s in name for s in EXCLUDE_DIR_SUBSTRINGS)


def excluded_file(name: str) -> bool:
    if name in EXCLUDE_FILE_NAMES:
        return True
    return any(name.endswith(suf) for suf in EXCLUDE_FILE_SUFFIXES)


def count_file_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            count = 0
            for _ in f:
                count += 1
                if count >= MAX_LINES_PER_FILE:
                    return MAX_LINES_PER_FILE
            return count
    except (OSError, ValueError):
        return 0


def language_lines(repo: Path) -> Counter[str]:
    counter: Counter[str] = Counter()
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if not excluded_dir(d)]
        for fname in files:
            if excluded_file(fname):
                continue
            ext = Path(fname).suffix.lower()
            info = LANG_INFO.get(ext)
            if not info:
                continue
            lines = count_file_lines(Path(root) / fname)
            if lines:
                counter[info[0]] += lines
    return counter

# --- RENDERING --------------------------------------------------------------

THEME_STYLE = """
  .bg     { fill: #ffffff; stroke: #e1e4e8; }
  .title  { fill: #2f80ed; font-weight: 600; }
  .label  { fill: #434d58; }
  .value  { fill: #434d58; font-weight: 600; }
  .footer { fill: #6e7781; }
  .bar-bg { fill: #ddd; }
  @media (prefers-color-scheme: dark) {
    .bg     { fill: #0d1117; stroke: #30363d; }
    .title  { fill: #58a6ff; }
    .label  { fill: #c9d1d9; }
    .value  { fill: #c9d1d9; }
    .footer { fill: #8b949e; }
    .bar-bg { fill: #30363d; }
  }
"""


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_stats_svg(stats: dict, footer: str) -> str:
    rows = [
        ("Active repos",       fmt_int(stats["repos"])),
        ("Commits authored",   fmt_int(stats["commits"])),
        ("Lines of code",      fmt_int(stats["loc"])),
        ("Active days",        fmt_int(stats["active_days"])),
        ("Languages used",     fmt_int(stats["languages"])),
    ]
    width, height = 420, 215
    title_y = 35
    row_start_y = 70
    row_step = 25

    row_svg = []
    for i, (label, value) in enumerate(rows):
        y = row_start_y + i * row_step
        row_svg.append(
            f'<text x="25" y="{y}" class="label" font-size="14">{label}</text>'
            f'<text x="{width - 25}" y="{y}" class="value" font-size="14" '
            f'text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,monospace">{value}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <style>{THEME_STYLE}</style>
  <rect x="0.5" y="0.5" rx="6" width="{width - 1}" height="{height - 1}" class="bg" stroke-width="1"/>
  <text x="25" y="{title_y}" class="title" font-size="18">Local stats</text>
  {''.join(row_svg)}
  <text x="25" y="{height - 15}" class="footer" font-size="10">{footer}</text>
</svg>
"""


def render_langs_svg(counter: Counter[str], footer: str) -> str:
    width, height = 360, 292
    total = sum(counter.values()) or 1

    # Top 10 languages — rest aggregated as "Other".
    top = counter.most_common(10)
    shown_total = sum(v for _, v in top)
    other = total - shown_total
    items = list(top)
    if other > 0:
        items.append(("Other", other))

    color_for = {name: LANG_INFO[ext][1]
                 for ext, (n, _) in LANG_INFO.items() for name in [n]}
    color_for["Other"] = "#8b949e"

    # Stacked bar across the top.
    bar_x, bar_y, bar_w, bar_h = 25, 60, width - 50, 8
    segs = []
    cursor = 0.0
    for name, val in items:
        seg_w = bar_w * (val / total)
        segs.append(
            f'<rect x="{bar_x + cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" '
            f'height="{bar_h}" fill="{color_for.get(name, "#8b949e")}"/>'
        )
        cursor += seg_w
    segs.insert(
        0,
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="{bar_h / 2}" class="bar-bg"/>'
    )
    # Continuous shimmer
    shimmer_w = 90
    shimmer = (
        f'<rect x="{-shimmer_w}" y="{bar_y}" width="{shimmer_w}" '
        f'height="{bar_h}" fill="url(#shimmer-grad)">'
        f'<animate attributeName="x" '
        f'values="{-shimmer_w};{width};{width}" '
        f'keyTimes="0;0.25;1" dur="6s" begin="1.5s" '
        f'repeatCount="indefinite"/>'
        f'</rect>'
    )
    # Bar grows in via an animated clipPath so segments unmask left-to-right.
    bar_group = (
        f'<defs>'
        f'<clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" '
        f'width="0" height="{bar_h}" rx="{bar_h / 2}">'
        f'<animate attributeName="width" from="0" to="{bar_w}" '
        f'dur="1.2s" begin="0.1s" fill="freeze"/>'
        f'</rect></clipPath>'
        f'<linearGradient id="shimmer-grad" x1="0%" x2="100%">'
        f'<stop offset="0%" stop-color="white" stop-opacity="0"/>'
        f'<stop offset="50%" stop-color="white" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="white" stop-opacity="0"/>'
        f'</linearGradient>'
        f'</defs>'
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="{bar_h / 2}" class="bar-bg"/>'
        f'<g clip-path="url(#barclip)">{"".join(segs)}{shimmer}</g>'
    )

    # Legend: 2 columns × ceil(items / 2) rows. Stagger-fades after the bar.
    col_w = (width - 50) // 2
    legend_x0 = 25
    legend_y0 = 105
    row_h = 28
    legend_svg = []
    for i, (name, val) in enumerate(items):
        col = i % 2
        row = i // 2
        cx = legend_x0 + col * col_w
        cy = legend_y0 + row * row_h
        pct = 100 * val / total
        color = color_for.get(name, "#8b949e")
        delay = 0.4 + i * 0.06
        legend_svg.append(
            f'<g transform="translate({cx}, {cy})" opacity="0">'
            f'<circle cx="6" cy="-4" r="5" fill="{color}"/>'
            f'<text x="18" y="0" class="label" font-size="12">{name}</text>'
            f'<text x="{col_w - 10}" y="0" class="value" font-size="12" '
            f'text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,monospace">'
            f'{pct:.1f}%</text>'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{delay:.2f}s" dur="0.45s" fill="freeze"/>'
            f'</g>'
        )

    # Bilingual title that cross-fades between EN and PT-BR on a 12s loop.
    title_keytimes = "0;0.42;0.5;0.92;1"
    title_dur = "12s"
    title_svg = (
        f'<text x="25" y="35" class="title" font-size="18" opacity="1">'
        f'Most used languages'
        f'<animate attributeName="opacity" values="1;1;0;0;1" '
        f'keyTimes="{title_keytimes}" dur="{title_dur}" '
        f'repeatCount="indefinite"/>'
        f'</text>'
        f'<text x="25" y="35" class="title" font-size="18" opacity="0">'
        f'Linguagens mais usadas'
        f'<animate attributeName="opacity" values="0;0;1;1;0" '
        f'keyTimes="{title_keytimes}" dur="{title_dur}" '
        f'repeatCount="indefinite"/>'
        f'</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <style>{THEME_STYLE}</style>
  <rect x="0.5" y="0.5" rx="6" width="{width - 1}" height="{height - 1}" class="bg" stroke-width="1"/>
  {title_svg}
  {bar_group}
  {''.join(legend_svg)}
  <text x="25" y="{height - 15}" class="footer" font-size="10">{footer}</text>
</svg>
"""

# --- MAIN -------------------------------------------------------------------

def main() -> None:
    email = git_email()
    repos = find_repos(PROJECTS_DIR)
    if not repos:
        raise SystemExit(f"No git repos found under {PROJECTS_DIR}")

    total_commits = 0
    active_days: set[str] = set()
    lang_counter: Counter[str] = Counter()

    for repo in repos:
        c, days = commits_for(repo, email)
        total_commits += c
        active_days |= days
        lang_counter.update(language_lines(repo))

    stats = {
        "repos":        len(repos),
        "commits":      total_commits,
        "loc":          sum(lang_counter.values()),
        "active_days":  len(active_days),
        "languages":    len(lang_counter),
    }

    today = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()
    footer = f"Generated locally from {len(repos)} repos · {today}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "langs.svg").write_text(render_langs_svg(lang_counter, footer))
    # render_stats_svg(stats, footer) is kept for reference — re-enable by
    # writing it to OUTPUT_DIR / "stats.svg" if you ever want the box back.

    print(f"Wrote {OUTPUT_DIR}/langs.svg")
    print(f"  repos: {stats['repos']}, commits: {stats['commits']}, "
          f"loc: {stats['loc']:,}, active days: {stats['active_days']}, "
          f"languages: {stats['languages']}")
    for name, val in lang_counter.most_common(10):
        pct = 100 * val / stats["loc"]
        print(f"    {name:12s} {val:>10,}  {pct:5.1f}%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the profile README art: two theme-aware hero banners, a contributions
card that counts public + private work, and a framed Ache Desktop capture.
Text is converted to SVG paths so the typography is identical everywhere
GitHub renders the images."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import urllib.request
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = Path(__file__).resolve().parent / ".cache"
FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/"
    "bricolagegrotesque/BricolageGrotesque%5Bopsz,wdth,wght%5D.ttf"
)
FONT_PATH = CACHE / "BricolageGrotesque.ttf"
SCREENSHOT_URL = "https://ache.lol/homepage/product-desktop-working.webp"
SCREENSHOT_PATH = CACHE / "ache-desktop.webp"
CONTRIB_URL = "https://github-contributions-api.jogruber.de/v4/EOSKILLZ?y=last"

W, H = 1040, 545
PAD = 56
UPEM = 1000


def ensure(url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(path, "wb") as fh:
            fh.write(resp.read())
    return path


@lru_cache(maxsize=None)
def calendar() -> dict:
    """GitHub's contribution graph, public and private, last 12 months."""
    req = urllib.request.Request(CONTRIB_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


@lru_cache(maxsize=None)
def font_instance(weight: int, opsz: int) -> tuple[TTFont, hb.Font]:
    """Return an instanced TTFont plus a HarfBuzz font at the same instance."""
    base = TTFont(ensure(FONT_URL, FONT_PATH))
    inst = instantiateVariableFont(
        base, {"wght": weight, "opsz": opsz, "wdth": 100}, inplace=False
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
    inst.save(tmp.name)
    tmp.close()
    blob = hb.Blob.from_file_path(tmp.name)
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (UPEM, UPEM)
    return inst, hb_font


def shape(text: str, weight: int, opsz: int, tracking: float):
    """Shape text, returning (glyph paths, advance width) in font units."""
    inst, hb_font = font_instance(weight, opsz)
    glyph_order = inst.getGlyphOrder()
    glyph_set = inst.getGlyphSet()

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})

    paths = []
    pen_x = 0.0
    track_units = tracking * UPEM
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gid = info.codepoint
        name = glyph_order[gid]
        svg_pen = SVGPathPen(glyph_set)
        pen = RoundingPen(svg_pen, roundFunc=lambda v: round(v, 1))
        glyph_set[name].draw(pen)
        d = svg_pen.getCommands()
        if d:
            x = pen_x + pos.x_offset
            y = -pos.y_offset
            paths.append((d, x, y))
        pen_x += pos.x_advance + track_units
    width = pen_x - track_units if paths else 0.0
    return paths, width


def text(
    s: str,
    x: float,
    y: float,
    size: float,
    fill: str,
    *,
    weight: int = 500,
    opsz: int = 24,
    tracking: float = 0.0,
    anchor: str = "start",
    opacity: float = 1.0,
) -> tuple[str, float]:
    paths, width_units = shape(s, weight, opsz, tracking)
    width = width_units * size / UPEM
    if anchor == "end":
        x -= width
    elif anchor == "middle":
        x -= width / 2
    scale = size / UPEM
    opacity_attr = f' fill-opacity="{opacity}"' if opacity != 1.0 else ""
    out = [f'<g fill="{fill}"{opacity_attr}>']
    for d, gx, gy in paths:
        tx = x + gx * scale
        ty = y + gy * scale
        out.append(
            f'<path d="{d}" transform="translate({tx:.2f} {ty:.2f}) scale({scale:.5f} {-scale:.5f})"/>'
        )
    out.append("</g>")
    return "".join(out), width


THEME = {
    "light": {
        "bg": "#F2EDE6",
        "ink": "#17130F",
        "muted": "#6C6157",
        "hair": "#17130F",
        "hair_op": 0.14,
        "ember": "#D9491F",
        "ember_small": "#B43E1B",
        "glow": 0.05,
    },
    "dark": {
        "bg": "#0A0A0A",
        "ink": "#F7EEE9",
        "muted": "#A89D92",
        "hair": "#F7EEE9",
        "hair_op": 0.16,
        "ember": "#FF6B4A",
        "ember_small": "#FF6B4A",
        "glow": 0.09,
    },
}


def hero(theme_name: str) -> str:
    c = THEME[theme_name]
    right = W - PAD
    body = [f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']

    # Diffuse ember glow, restrained.
    body.append(
        f"""<radialGradient id="glow" cx="0.74" cy="0.36" r="0.62">
      <stop offset="0" stop-color="{c['ember']}" stop-opacity="{c['glow']}"/>
      <stop offset="1" stop-color="{c['ember']}" stop-opacity="0"/>
    </radialGradient>
    <rect width="{W}" height="{H}" fill="url(#glow)"/>"""
    )

    # Header: wordmark left, place right, hairline under.
    body.append(f'<rect x="{PAD}" y="44" width="10" height="10" fill="{c["ember"]}"/>')
    brand, brand_w = text(
        "SKILLZ", PAD + 22, 56, 20, c["ink"], weight=600, opsz=48, tracking=0.06
    )
    body.append(brand)
    handle, _ = text(
        "/ EOSKILLZ", PAD + 22 + brand_w + 12, 56, 15, c["muted"], weight=500,
        opsz=24, tracking=0.04,
    )
    body.append(handle)
    place, _ = text(
        "NEW YORK, US", right, 56, 14, c["muted"], weight=500, opsz=24,
        tracking=0.10, anchor="end",
    )
    body.append(place)
    body.append(
        f'<rect x="{PAD}" y="84" width="{W - PAD * 2}" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )

    # Eyebrow
    body.append(f'<rect x="{PAD}" y="133" width="8" height="8" fill="{c["ember"]}"/>')
    eyebrow, _ = text(
        "INDEPENDENT SOFTWARE ENGINEER", PAD + 20, 142, 15, c["muted"], weight=500,
        opsz=24, tracking=0.14,
    )
    body.append(eyebrow)

    # Headline: one line, evenly centered, second phrase carries the accent.
    size, track = 168, -0.045
    _, total_units = shape("I build Ache.", 600, 96, track)
    _, name_units = shape("Ache.", 600, 96, track)
    total_w = total_units * size / UPEM
    name_w = name_units * size / UPEM
    start = (W - total_w) / 2
    lead, _ = text("I build ", start, 330, size, c["ink"], weight=600, opsz=96, tracking=track)
    name, _ = text("Ache.", start + total_w - name_w, 330, size, c["ember"], weight=600, opsz=96, tracking=track)
    body.append(lead)
    body.append(name)

    sub, _ = text(
        "AI workspace, API, CLI, and desktop app.", W / 2, 402, 30, c["muted"],
        weight=500, opsz=32, tracking=0.005, anchor="middle",
    )
    body.append(sub)

    # Footer strip
    body.append(
        f'<rect x="{PAD}" y="468" width="{W - PAD * 2}" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )
    foot_l, _ = text(
        "CHAT · CODE · AUTOMATE", PAD, 507, 15, c["muted"], weight=500, opsz=24,
        tracking=0.10,
    )
    foot_r, _ = text(
        "ACHE.LOL", right, 507, 15, c["ember_small"], weight=600, opsz=24,
        tracking=0.10, anchor="end",
    )
    body.append(foot_l)
    body.append(foot_r)

    title = "Skillz — independent software engineer. I build Ache."
    desc = (
        "Warm editorial hero on a paper background: I build Ache. "
        "Ache is an AI workspace, API, CLI, and desktop app."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


CARD_H = 425
CARD_LEVELS = {
    "light": ["#E4DBD0", "#F2C4B2", "#E99373", "#DF6B45", "#D9491F"],
    "dark": ["#1B1713", "#59291B", "#A34226", "#E05533", "#FF6B4A"],
}


def contributions(theme_name: str) -> str:
    """Total contributions card: public and private, with a year heatmap."""
    c = THEME[theme_name]
    data = calendar()
    days = data["contributions"]
    total = data["total"]["lastYear"]

    inner = W - PAD * 2
    gap = 3
    first = dt.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7  # Monday=0 -> Sunday=0
    cols = -(-(offset + len(days)) // 7)
    pitch = (inner + gap) / cols
    cell = pitch - gap
    top = 252

    counts = sorted(d["count"] for d in days if d["count"] > 0)

    def level(n: int) -> int:
        if n <= 0:
            return 0
        return 1 + sum(
            n > counts[min(len(counts) - 1, int(len(counts) * p))]
            for p in (0.25, 0.5, 0.75)
        )

    fills = CARD_LEVELS[theme_name]
    body = [f'<rect width="{W}" height="{CARD_H}" fill="{c["bg"]}"/>']
    body.append(f'<rect x="{PAD}" y="44" width="10" height="10" fill="{c["ember"]}"/>')
    label, _ = text(
        "GITHUB ACTIVITY", PAD + 22, 56, 18, c["ink"], weight=600, opsz=48,
        tracking=0.16,
    )
    body.append(label)
    scope, _ = text(
        "PUBLIC + PRIVATE", W - PAD, 56, 14, c["ember_small"], weight=600,
        opsz=24, tracking=0.10, anchor="end",
    )
    body.append(scope)
    body.append(
        f'<rect x="{PAD}" y="84" width="{inner}" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )

    number, number_w = text(
        f"{total:,}", PAD - 4, 214, 138, c["ember"], weight=600, opsz=96,
        tracking=-0.03,
    )
    body.append(number)
    head, _ = text(
        "CONTRIBUTIONS", PAD + number_w + 26, 182, 19, c["ink"], weight=600,
        opsz=48, tracking=0.12,
    )
    body.append(head)
    sub, _ = text(
        "IN THE LAST 12 MONTHS", PAD + number_w + 26, 208, 13, c["muted"],
        weight=500, opsz=24, tracking=0.12,
    )
    body.append(sub)

    for i, day in enumerate(days):
        idx = offset + i
        x = PAD + (idx // 7) * pitch
        y = top + (idx % 7) * pitch
        body.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" '
            f'rx="{cell * 0.18:.2f}" fill="{fills[level(day["count"])]}"/>'
        )

    grid_bottom = top + 7 * pitch - gap
    left_month, _ = text(
        first.strftime("%b %Y").upper(), PAD, grid_bottom + 25, 13, c["muted"],
        weight=500, opsz=24, tracking=0.10,
    )
    right_month, _ = text(
        dt.date.fromisoformat(days[-1]["date"]).strftime("%b %Y").upper(),
        W - PAD, grid_bottom + 25, 13, c["muted"], weight=500, opsz=24,
        tracking=0.10, anchor="end",
    )
    body.append(left_month)
    body.append(right_month)

    title = f"{total:,} contributions in the last 12 months"
    desc = (
        "A year of GitHub activity counted from the contribution graph, "
        "including work in private repositories."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{CARD_H}" '
        f'viewBox="0 0 {W} {CARD_H}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


def frame_screenshot() -> None:
    """Round the Ache Desktop capture and give it a hairline + soft shadow."""
    src = Image.open(ensure(SCREENSHOT_URL, SCREENSHOT_PATH)).convert("RGBA")
    shot_w, shot_h = src.size
    radius = 18
    pad = 36
    canvas_w, canvas_h = shot_w + pad * 2, shot_h + pad * 2

    mask = Image.new("L", (shot_w, shot_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, shot_w - 1, shot_h - 1), radius=radius, fill=255
    )

    # Shadow on a transparent canvas.
    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rounded_rectangle(
        (pad, pad + 8, pad + shot_w, pad + shot_h + 8),
        radius=radius,
        fill=(10, 10, 10, 64),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
    shadow.alpha_composite(shadow_layer)

    src.putalpha(mask)
    shadow.alpha_composite(src, (pad, pad))

    # Hairline border.
    border = ImageDraw.Draw(shadow)
    border.rounded_rectangle(
        (pad, pad, pad + shot_w - 1, pad + shot_h - 1),
        radius=radius,
        outline=(255, 255, 255, 34),
        width=1,
    )

    ASSETS.mkdir(parents=True, exist_ok=True)
    shadow.save(ASSETS / "ache-desktop.webp", "WEBP", quality=92, method=6)
    print("wrote", ASSETS / "ache-desktop.webp", shadow.size)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        hero_path = ASSETS / f"hero-{theme}.svg"
        hero_path.write_text(hero(theme), encoding="utf-8")
        print("wrote", hero_path, f"{hero_path.stat().st_size / 1024:.1f} KiB")

        card_path = ASSETS / f"contributions-{theme}.svg"
        card_path.write_text(contributions(theme), encoding="utf-8")
        print("wrote", card_path, f"{card_path.stat().st_size / 1024:.1f} KiB")
    frame_screenshot()


if __name__ == "__main__":
    main()

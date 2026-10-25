#!/usr/bin/env python3
"""Build the profile README art: two theme-aware hero banners and a framed
Ache Desktop capture. Text is converted to SVG paths so the typography is
identical everywhere GitHub renders the images."""

from __future__ import annotations

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

W, H = 1600, 740
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
    body = [f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']

    # Diffuse ember glow, restrained.
    body.append(
        f"""<radialGradient id="glow" cx="0.78" cy="0.42" r="0.55">
      <stop offset="0" stop-color="{c['ember']}" stop-opacity="{c['glow']}"/>
      <stop offset="1" stop-color="{c['ember']}" stop-opacity="0"/>
    </radialGradient>
    <rect width="{W}" height="{H}" fill="url(#glow)"/>"""
    )

    # Header rule
    body.append(
        f'<rect x="72" y="112" width="1456" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )
    body.append(f'<rect x="72" y="52" width="12" height="12" fill="{c["ember"]}"/>')
    skillz, skillz_w = text(
        "SKILLZ", 98, 76, 24, c["ink"], weight=600, opsz=48, tracking=0.06
    )
    body.append(skillz)
    handle, _ = text(
        "/ EOSKILLZ", 98 + skillz_w + 14, 76, 18, c["muted"], weight=500, opsz=24,
        tracking=0.04,
    )
    body.append(handle)
    ny, _ = text(
        "NEW YORK, US", 1528, 76, 17, c["muted"], weight=500, opsz=24,
        tracking=0.10, anchor="end",
    )
    body.append(ny)

    # Eyebrow
    body.append(f'<rect x="72" y="178" width="9" height="9" fill="{c["ember"]}"/>')
    eyebrow, _ = text(
        "INDEPENDENT SOFTWARE ENGINEER", 94, 190, 18, c["muted"], weight=500,
        opsz=24, tracking=0.14,
    )
    body.append(eyebrow)

    # Headline: two-line landing, second line carries the accent.
    line1, _ = text(
        "I build", 68, 392, 226, c["ink"], weight=600, opsz=96, tracking=-0.045
    )
    line2, _ = text(
        "Ache.", 68, 588, 226, c["ember"], weight=600, opsz=96, tracking=-0.050
    )
    body.append(line1)
    body.append(line2)

    # Right column: selected work
    body.append(
        f'<rect x="1010" y="176" width="1" height="330" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )
    label, _ = text(
        "SELECTED WORK", 1060, 200, 15, c["muted"], weight=600, opsz=24,
        tracking=0.16,
    )
    body.append(label)

    rows = [
        ("ACHE", "LIVE", True, True),
        ("LOCALOWL", "OPEN SOURCE", False, True),
        ("PULSE", "100K USERS", False, False),
        ("YAP.REST", "300 USERS", False, False),
    ]
    ys = [272, 332, 392, 452]
    for i, ((name, status, active, bright), y) in enumerate(zip(rows, ys)):
        if active:
            body.append(f'<circle cx="1042" cy="{y - 10}" r="4" fill="{c["ember"]}"/>')
        name_svg, _ = text(
            name, 1060, y, 30, c["ink"], weight=600, opsz=48, tracking=-0.005
        )
        body.append(name_svg)
        status_svg, _ = text(
            status, 1528, y, 14,
            c["ember_small"] if bright else c["muted"],
            weight=600, opsz=24, tracking=0.10, anchor="end",
        )
        body.append(status_svg)
        if i < len(rows) - 1:
            body.append(
                f'<rect x="1060" y="{y + 18}" width="468" height="1" fill="{c["hair"]}" opacity="{c["hair_op"] * 0.7}"/>'
            )

    # Footer rule + labels
    body.append(
        f'<rect x="72" y="650" width="1456" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )
    foot_l, _ = text(
        "CHAT · CODE · AUTOMATE", 72, 696, 17, c["muted"], weight=500, opsz=24,
        tracking=0.10,
    )
    foot_r, _ = text(
        "ACHE.LOL", 1528, 696, 17, c["ember_small"], weight=600, opsz=24,
        tracking=0.10, anchor="end",
    )
    body.append(foot_l)
    body.append(foot_r)

    title = "Skillz — independent software engineer. I build Ache."
    desc = (
        "Warm editorial hero: I build Ache. Selected work: Ache (live), "
        "LocalOwl (open source), Pulse (100K users), YAP.REST (300 users)."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">'
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
        path = ASSETS / f"hero-{theme}.svg"
        path.write_text(hero(theme), encoding="utf-8")
        print("wrote", path, f"{path.stat().st_size / 1024:.1f} KiB")
    frame_screenshot()


if __name__ == "__main__":
    main()

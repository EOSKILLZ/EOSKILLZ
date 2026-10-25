#!/usr/bin/env python3
"""Build the profile README art: theme- and width-aware hero banners, a
contributions card that counts public + private work, a badge wall, and a
framed Ache Desktop capture. Text is converted to SVG paths so the typography
is identical everywhere GitHub renders the images."""

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
MONO_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/"
    "jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"
)
MONO_PATH = CACHE / "JetBrainsMono.ttf"
FONTS = {
    "display": (FONT_URL, FONT_PATH, {"opsz": 24, "wdth": 100}),
    "mono": (MONO_URL, MONO_PATH, {}),
}
SCREENSHOT_URL = "https://ache.lol/homepage/product-desktop-working.webp"
SCREENSHOT_PATH = CACHE / "ache-desktop.webp"
CONTRIB_URL = "https://github-contributions-api.jogruber.de/v4/EOSKILLZ?y=last"

W, H = 1040, 600
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
def font_instance(family: str, weight: int, opsz: int) -> tuple[TTFont, hb.Font]:
    """Return an instanced TTFont plus a HarfBuzz font at the same instance."""
    url, path, axes = FONTS[family]
    base = TTFont(ensure(url, path))
    settings = {"wght": weight, **axes}
    if "opsz" in settings:
        settings["opsz"] = opsz
    inst = instantiateVariableFont(base, settings, inplace=False)
    tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
    inst.save(tmp.name)
    tmp.close()
    blob = hb.Blob.from_file_path(tmp.name)
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (UPEM, UPEM)
    return inst, hb_font


def shape(text: str, weight: int, opsz: int, tracking: float, family: str = "display"):
    """Shape text, returning (glyph paths, advance width) in font units."""
    inst, hb_font = font_instance(family, weight, opsz)
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
    family: str = "display",
) -> tuple[str, float]:
    paths, width_units = shape(s, weight, opsz, tracking, family)
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
        "bg": "#FBFAF8",
        "ink": "#172126",
        "muted": "#6E7274",
        "hair": "#172126",
        "hair_op": 0.12,
        "ember": "#E4572E",
        "ember_deep": "#B23A12",
        "ember_light": "#F59A4B",
        "teal": "#087B96",
        "glow": 0.0,
        "grid": 0.050,
    },
    "dark": {
        "bg": "#0D0F10",
        "ink": "#F5F2ED",
        "muted": "#9B9C9B",
        "hair": "#F5F2ED",
        "hair_op": 0.14,
        "ember": "#FF7A4D",
        "ember_deep": "#E2542A",
        "ember_light": "#FFB27A",
        "teal": "#4FC3D9",
        "glow": 0.08,
        "grid": 0.055,
    },
}


GRID_STEP = (W - PAD * 2) / 12
MARK_APEX = 800
MARK_TOP = 190
MARK_SLOPE = 0.543  # matches the chevron in the Ache app icon
MARK_STROKE = 48
MARK_DOT_R = 21


def hero(theme_name: str) -> str:
    c = THEME[theme_name]
    right = W - PAD
    body = [f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']

    # Technical grid, barely there; the columns land on the frame.
    body.append(f'<g stroke="{c["hair"]}" stroke-opacity="{c["grid"]}" stroke-width="1.2">')
    for i in range(13):
        x = PAD + GRID_STEP * i
        body.append(f'<path d="M{x:.2f} 84V{H}"/>')
    y = 84
    while y < H:
        body.append(f'<path d="M{PAD} {y}H{right}"/>')
        y += 80
    body.append("</g>")

    # Ember glow behind the mark: dark mode only, and barely.
    if c["glow"]:
        body.append(
            f"""<radialGradient id="glow" cx="0.80" cy="0.34" r="0.55">
      <stop offset="0" stop-color="{c['ember']}" stop-opacity="{c['glow']}"/>
      <stop offset="1" stop-color="{c['ember']}" stop-opacity="0"/>
    </radialGradient>
    <rect width="{W}" height="{H}" fill="url(#glow)"/>"""
        )

    # The Ache mark, monumental: the right leg runs off the frame.
    half = (H - MARK_TOP) * MARK_SLOPE
    body.append(
        f"""<linearGradient id="mark" x1="0.1" y1="1" x2="0.9" y2="0">
      <stop offset="0" stop-color="{c['ember_deep']}"/>
      <stop offset="1" stop-color="{c['ember_light']}"/>
    </linearGradient>
    <path d="M{MARK_APEX - half:.1f} {H} L{MARK_APEX:.1f} {MARK_TOP} L{MARK_APEX + half:.1f} {H}"
      fill="none" stroke="url(#mark)" stroke-width="{MARK_STROKE}"
      stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="{MARK_APEX:.1f}" cy="{MARK_TOP - MARK_STROKE / 2 - 12 - MARK_DOT_R}"
      r="{MARK_DOT_R}" fill="{c['ember_light']}"/>"""
    )

    # Frame: wordmark, place, hairline.
    body.append(f'<rect x="{PAD}" y="42" width="8" height="8" fill="{c["ember"]}"/>')
    brand, brand_w = text(
        "SKILLZ", PAD + 18, 52, 17, c["ink"], weight=600, opsz=48, tracking=0.06
    )
    body.append(brand)
    handle, _ = text(
        "/ EOSKILLZ", PAD + 18 + brand_w + 12, 51, 12, c["muted"], weight=400,
        tracking=0.14, family="mono",
    )
    body.append(handle)
    place, _ = text(
        "NEW YORK, US", right, 51, 12, c["muted"], weight=400, tracking=0.14,
        anchor="end", family="mono",
    )
    body.append(place)
    body.append(
        f'<rect x="{PAD}" y="84" width="{W - PAD * 2}" height="1" fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )

    # Eyebrow: tiny, technical, aligned to the frame.
    body.append(f'<rect x="{PAD}" y="238" width="7" height="7" fill="{c["ember"]}"/>')
    eyebrow, _ = text(
        "INDEPENDENT SOFTWARE ENGINEER", PAD + 16, 245, 12, c["muted"],
        weight=400, tracking=0.18, family="mono",
    )
    body.append(eyebrow)

    # Headline: quiet verb, loud name.
    build, _ = text(
        "I build", PAD, 348, 48, c["ink"], weight=500, opsz=48, tracking=-0.005
    )
    body.append(build)

    size, track = 190, -0.05
    _, name_units = shape("Ache", 600, 96, track)
    name_w = name_units * size / UPEM
    name, _ = text("Ache", PAD + 2, 508, size, c["ink"], weight=600, opsz=96, tracking=track)
    period, _ = text(
        ".", PAD + 2 + name_w + size * 0.026, 508, size, c["teal"], weight=600,
        opsz=96, tracking=track,
    )
    body.append(name)
    body.append(period)

    # Footer strip: what it is, where to go.
    foot_l, foot_l_w = text(
        "AI WORKSPACE / API / CLI / DESKTOP", PAD, 578, 12, c["muted"],
        weight=400, tracking=0.14, family="mono",
    )
    body.append(foot_l)
    foot_r, _ = text(
        " · ACHE.LOL", PAD + foot_l_w, 578, 12, c["teal"], weight=500,
        tracking=0.14, family="mono",
    )
    body.append(foot_r)

    title = "Skillz — independent software engineer. I build Ache."
    desc = (
        "The Ache chevron mark in ember on a fine technical grid, with the line "
        "I build Ache. Ache is an AI workspace, API, CLI, and desktop app."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


NARROW_W, NARROW_H = 360, 232


def hero_narrow(theme_name: str) -> str:
    """The phone artboard: type-led, no grid, the mark cut down to a glyph."""
    c = THEME[theme_name]
    width, height = NARROW_W, NARROW_H
    pad = 22
    right = width - pad
    body = [f'<rect width="{width}" height="{height}" fill="{c["bg"]}"/>']

    body.append(f'<rect x="{pad}" y="21" width="6" height="6" fill="{c["ember"]}"/>')
    brand, _ = text(
        "SKILLZ", pad + 14, 28, 11, c["ink"], weight=600, opsz=48, tracking=0.08
    )
    body.append(brand)

    # The mark, small enough to read as a signature rather than a poster.
    apex_x, apex_y = right - 10, 20
    half = 28 * MARK_SLOPE
    body.append(
        f"""<linearGradient id="mark" x1="0.1" y1="1" x2="0.9" y2="0">
      <stop offset="0" stop-color="{c['ember_deep']}"/>
      <stop offset="1" stop-color="{c['ember_light']}"/>
    </linearGradient>
    <path d="M{apex_x - half:.1f} {apex_y + 28} L{apex_x} {apex_y} L{apex_x + half:.1f} {apex_y + 28}"
      fill="none" stroke="url(#mark)" stroke-width="10"
      stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="{apex_x}" cy="{apex_y - 5 - 2 - 4}" r="4" fill="{c['ember_light']}"/>"""
    )

    body.append(
        f'<rect x="{pad}" y="44" width="{width - pad * 2}" height="1" '
        f'fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )

    build, _ = text(
        "I build", pad, 106, 21, c["ink"], weight=500, opsz=48, tracking=-0.005
    )
    body.append(build)

    size, track = 108, -0.05
    _, name_units = shape("Ache", 600, 96, track)
    name_w = name_units * size / UPEM
    name, _ = text("Ache", pad, 200, size, c["ink"], weight=600, opsz=96, tracking=track)
    period, _ = text(
        ".", pad + name_w + size * 0.026, 200, size, c["teal"], weight=600,
        opsz=96, tracking=track,
    )
    body.append(name)
    body.append(period)

    foot, _ = text(
        "NEW YORK · AI WORKSPACE", pad, 222, 9.5, c["muted"], weight=400,
        tracking=0.14, family="mono",
    )
    body.append(foot)
    link, _ = text(
        "ACHE.LOL", right, 222, 9.5, c["teal"], weight=500, tracking=0.14,
        anchor="end", family="mono",
    )
    body.append(link)

    title = "Skillz — independent software engineer. I build Ache."
    desc = "I build Ache. Ache is an AI workspace, API, CLI, and desktop app."
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


CARD_W, CARD_H = 1040, 304


STACK = [
    ("typescript", "TypeScript"),
    ("python", "Python"),
    ("react", "React"),
    ("vite", "Vite"),
    ("nodedotjs", "Node.js"),
    ("electron", "Electron"),
    ("tailwindcss", "Tailwind"),
    ("github", "GitHub"),
    ("express", "Express"),
    ("sqlite", "SQLite"),
    ("docker", "Docker"),
    ("cloudflare", "Cloudflare"),
]
ICON_URL = "https://cdn.simpleicons.org/{slug}/F59A4B"


@lru_cache(maxsize=None)
def icon_path(slug: str) -> str:
    """The simple-icons glyph for a tool, as a single SVG path."""
    path = CACHE / "icons" / f"{slug}.svg"
    text = ensure(ICON_URL.format(slug=slug), path).read_text(encoding="utf-8")
    return text.split(' d="', 1)[1].split('"', 1)[0]


def badges(theme_name: str, narrow: bool = False) -> str:
    """A badge wall drawn at the width it is rendered at, never scaled down."""
    c = THEME[theme_name]
    if narrow:
        width, pad, cols, gap = 400, 20, 3, 8
        pad_y, chip_h, row_gap = 8, 40, 8
        icon_size, icon_x, label_x, label_size, label_base = 14, 10, 30, 12.5, 25
    else:
        width, pad, cols, gap = 1040, 56, 6, 10
        pad_y, chip_h, row_gap = 8, 36, 10
        icon_size, icon_x, label_x, label_size, label_base = 15, 14, 38, 12.5, 23
    chip_w = (width - pad * 2 - gap * (cols - 1)) / cols
    rows = -(-len(STACK) // cols)
    height = pad_y * 2 + chip_h * rows + row_gap * (rows - 1)
    chip_fill = "#172126" if theme_name == "light" else "#202325"
    label_fill = "#F5F2ED"
    stroke = (
        ""
        if theme_name == "light"
        else f' stroke="{c["ink"]}" stroke-opacity="0.14"'
    )
    scale = icon_size / 24

    body = []
    for i, (slug, label) in enumerate(STACK):
        x = pad + (i % cols) * (chip_w + gap)
        y = pad_y + (i // cols) * (chip_h + row_gap)
        body.append(
            f'<rect x="{x:.2f}" y="{y}" width="{chip_w:.2f}" height="{chip_h}" '
            f'rx="7" fill="{chip_fill}"{stroke}/>'
        )
        body.append(
            f'<g transform="translate({x + icon_x:.2f} {y + (chip_h - icon_size) / 2:.2f}) '
            f'scale({scale:.4f})"><path d="{icon_path(slug)}" fill="#F59A4B"/></g>'
        )
        name, _ = text(
            label, x + label_x, y + label_base, label_size, label_fill, weight=500,
            tracking=0.01, family="mono",
        )
        body.append(name)

    title = "Tools I build with"
    desc = ", ".join(label for _, label in STACK)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


def contributions(theme_name: str, narrow: bool = False) -> str:
    """The one number that includes private work, set as a title card."""
    c = THEME[theme_name]
    data = calendar()
    days = data["contributions"]
    total = data["total"]["lastYear"]
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    span = f"{first.strftime('%b %Y').upper()} — {last.strftime('%b %Y').upper()}"

    if narrow:
        width, height, pad = 320, 200, 20
        right = width - pad
        mark, mark_y = 6, 19
        label_size, label_x, label_base = 9, 32, 26
        scope_size = 8
        rule_y = 40
        number_size, number_x, number_base = 100, 17, 126
        cap_size, cap_x, cap_base = 9.5, 20, 164
        span_size, span_base = 9, 186
    else:
        width, height, pad = CARD_W, CARD_H, 56
        right = width - pad
        mark, mark_y = 10, 32
        label_size, label_x, label_base = 13, 78, 43
        scope_size = 12
        rule_y = 68
        number_size, number_x, number_base = 190, 50, 232
        cap_size, cap_x, cap_base = 12.5, 52, 286
        span_size, span_base = 12, 286

    body = [f'<rect width="{width}" height="{height}" fill="{c["bg"]}"/>']
    body.append(
        f'<rect x="{pad}" y="{mark_y}" width="{mark}" height="{mark}" fill="{c["ember"]}"/>'
    )
    label, _ = text(
        "GITHUB ACTIVITY", label_x, label_base, label_size, c["ink"], weight=500,
        tracking=0.18, family="mono",
    )
    body.append(label)
    scope, _ = text(
        "PUBLIC + PRIVATE", right, label_base, scope_size, c["muted"], weight=400,
        tracking=0.16, anchor="end", family="mono",
    )
    body.append(scope)
    body.append(
        f'<rect x="{pad}" y="{rule_y}" width="{width - pad * 2}" height="1" '
        f'fill="{c["hair"]}" opacity="{c["hair_op"]}"/>'
    )

    number, _ = text(
        f"{total:,}", number_x, number_base, number_size, c["ember"], weight=600,
        opsz=96, tracking=-0.03,
    )
    body.append(number)
    caption, _ = text(
        "CONTRIBUTIONS · LAST 12 MONTHS", cap_x, cap_base, cap_size, c["muted"],
        weight=400, tracking=0.16, family="mono",
    )
    body.append(caption)
    dates, _ = text(
        span, right, span_base, span_size, c["muted"], weight=400, tracking=0.14,
        anchor="end", family="mono",
    )
    body.append(dates)

    title = f"{total:,} contributions in the last 12 months"
    desc = "Public and private work counted from the GitHub contribution graph."
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{title}</title><desc id="desc">{desc}</desc>'
        + "".join(body)
        + "</svg>"
    )


def frame_screenshot() -> None:
    """Round the Ache Desktop capture and give it a hairline + soft shadow."""
    src = Image.open(ensure(SCREENSHOT_URL, SCREENSHOT_PATH)).convert("RGBA")

    # Ache's capture has a duplicated word in a collapsed tool row. Lift a clean
    # strip of the same pane over it so the screenshot reads properly.
    if src.size == (1920, 780):
        clean = src.crop((45, 158, 935, 186))
        src.paste(clean, (45, 188))

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
        for name, svg in (
            (f"hero-{theme}", hero(theme)),
            (f"hero-{theme}-narrow", hero_narrow(theme)),
            (f"contributions-{theme}", contributions(theme)),
            (f"contributions-{theme}-narrow", contributions(theme, narrow=True)),
            (f"badges-{theme}", badges(theme)),
            (f"badges-{theme}-narrow", badges(theme, narrow=True)),
        ):
            path = ASSETS / f"{name}.svg"
            path.write_text(svg, encoding="utf-8")
            print("wrote", path, f"{path.stat().st_size / 1024:.1f} KiB")
    frame_screenshot()


if __name__ == "__main__":
    main()

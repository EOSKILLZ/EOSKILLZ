# Profile art

`build_assets.py` generates the theme-aware hero banners, the contributions card, the tool-badge wall, and the framed Ache Desktop capture used by the profile README.

```bash
python3 -m pip install fonttools uharfbuzz pillow
python3 design/build_assets.py
```

The script downloads Bricolage Grotesque, JetBrains Mono, the Simple Icons glyphs, and the Ache Desktop capture into `design/.cache/` (ignored by git). Text is converted to SVG paths, so the art renders identically on GitHub without loading a web font.

Every piece ships in four files: light, dark, and a narrow artboard drawn for phones. The README picks between widths with a `max-width: 600px` media query and between themes with `prefers-color-scheme`.

The contributions card is a snapshot of the total from the GitHub contribution graph, public and private, over the last 12 months. Re-run the script to refresh it.

The screenshot framing also lifts a clean strip over a duplicated word in Ache's marketing capture; the patch is gated on the source image size.

# Profile art

`build_assets.py` generates the two theme-aware hero banners, the contributions card, and the framed Ache Desktop capture used by the profile README.

```bash
python3 -m pip install fonttools uharfbuzz pillow
python3 design/build_assets.py
```

The script downloads Bricolage Grotesque, JetBrains Mono, and the Ache Desktop capture into `design/.cache/` (ignored by git). Text is converted to SVG paths, so the art renders identically on GitHub without loading a web font.

The contributions card is a snapshot of the last 12 months from the GitHub contribution graph, public and private. Re-run the script to refresh it.

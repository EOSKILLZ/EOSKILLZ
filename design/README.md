# Profile art

`build_assets.py` generates the two theme-aware hero banners and the framed Ache Desktop capture used by the profile README.

```bash
python3 -m pip install fonttools uharfbuzz pillow
python3 design/build_assets.py
```

The script downloads Bricolage Grotesque and the Ache Desktop capture into `design/.cache/` (ignored by git). Text is converted to SVG paths, so the hero renders identically on GitHub without loading a web font.

# How the picture is made

`assets/mobius-ant-dark.svg` and `assets/mobius-ant-light.svg` are generated, not drawn.

```
pip install numpy shapely fonttools uharfbuzz
python src/build.py
```

- `geom.py`: the strip, r(u, v) = c(u) + v·d(u), whose ruling d turns by half a turn per lap, and a pinhole camera.
- `model.py`: which parts of the strip hide which; the ant (four ellipsoids, a tripod gait, elbowed antennae) walking the centre line.
- `build.py`: the SVG. The strip is static; the ant, its trail and the lit rulings are SMIL animations with one 20 s period, which is two laps.
- `glyphs.py`: text is set as outlines, so the SVG needs no fonts. Geist Mono, Noto Serif SC and EB Garamond (SIL Open Font License) are downloaded to `src/fonts/` on first run.

The ant spends one lap on the face turned towards you and the next on the face turned away, where it is drawn blurred, seen through the band. There is only one face.

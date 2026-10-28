# How the picture is made

`assets/mobius-ant-dark.svg` and `assets/mobius-ant-light.svg` are generated, not drawn.

```
pip install numpy shapely fonttools uharfbuzz
python src/build.py
```

- `geom.py`: the strip, r(u, v) = c(u) + v·d(u), whose ruling d turns by half a turn per lap, and a pinhole camera.
- `model.py`: which parts of the strip hide which; the ant (four ellipsoids, a tripod gait, elbowed antennae) walking a lane a little off the centre line; its point in the quotient chart.
- `build.py`: the SVG. The strip is static; the ant, its trail, the lit rulings and the formula are SMIL animations with one 20 s period, which is two laps.
- `glyphs.py`: text is set as outlines, so the SVG needs no fonts. Geist Mono, Noto Serif SC and EB Garamond (SIL Open Font License) are downloaded to `src/fonts/` on first run.

The ant spends one lap on the face turned towards you and the next on the face turned away, where it is drawn blurred, seen through the band. There is only one face.

The formula under the strip is the strip itself, M = [0,1]² / (0,y) ~ (1,1−y): a square whose left and right edges are glued with a flip. The second line is the ant's point in that square, updated at every step it takes. The dashed ruling is the glued edge. When the ant crosses it, x runs out at 1 and starts again at 0, y becomes 1 − y (0.400 ↔ 0.600), and the rule that did it lights up.

"""Text -> SVG path data (HarfBuzz shaping + fontTools outlines), so the SVG needs no fonts."""
import functools, io, pathlib, urllib.request
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.varLib import instancer

CJK_TEXT = "周行而不殆"
FONT_DIR = pathlib.Path(__file__).resolve().parent / "fonts"      # git-ignored; fetched on first use
CACHE = FONT_DIR / "_cache"
SOURCES = {  # Google Fonts repository, SIL Open Font License
    "GeistMono[wght].ttf": "ofl/geistmono/GeistMono%5Bwght%5D.ttf",
    "NotoSerifSC[wght].ttf": "ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf",
    "EBGaramond-Italic[wght].ttf": "ofl/ebgaramond/EBGaramond-Italic%5Bwght%5D.ttf",
}


def _fetch(name):
    f = FONT_DIR / name
    if not f.exists():
        FONT_DIR.mkdir(exist_ok=True)
        urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/" + SOURCES[name], f)
    return f


@functools.lru_cache(None)
def _load(name, axes):
    """Static instance of `name` at `axes`, cached on disk; CJK fonts are subset first (they are huge)."""
    CACHE.mkdir(exist_ok=True)
    key = CACHE / (name.replace("[", "_").replace("]", "_") + "".join(f"_{a}{v}" for a, v in axes) + ".ttf")
    if not key.exists():
        f = TTFont(_fetch(name))
        if name.startswith("NotoSerifSC"):
            from fontTools import subset
            opts = subset.Options(); opts.layout_features = ["*"]; opts.notdef_outline = True
            sub = subset.Subsetter(opts); sub.populate(text=CJK_TEXT); sub.subset(f)
        if axes and "fvar" in f:
            f = instancer.instantiateVariableFont(f, dict(axes))
        f.save(key)
    data = key.read_bytes()
    tt = TTFont(io.BytesIO(data))
    return tt, hb.Font(hb.Face(data)), tt["head"].unitsPerEm


def _fmt(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def text_path(text, name, size, x=0.0, y=0.0, axes=(), tracking=0.0, anchor="start"):
    """Horizontal text. Returns (d, width). `tracking` in em; baseline at y."""
    tt, font, upem = _load(name, tuple(sorted(axes)))
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    k = size / upem
    pen_x, parts = 0.0, []
    infos, poss = buf.glyph_infos, buf.glyph_positions
    width = sum(p.x_advance for p in poss) * k + tracking * size * max(len(poss) - 1, 0)
    x0 = x - (width if anchor == "end" else width / 2 if anchor == "middle" else 0)
    for i, (gi, gp) in enumerate(zip(infos, poss)):
        g = order[gi.codepoint]
        sp = SVGPathPen(gs, _fmt)
        tp = TransformPen(sp, (k, 0, 0, -k, x0 + pen_x + gp.x_offset * k, y - gp.y_offset * k))
        gs[g].draw(tp)
        parts.append(sp.getCommands())
        pen_x += gp.x_advance * k + tracking * size
    return "".join(parts), width


def vertical_cjk(text, name, size, x, y, axes=(), gap=0.25):
    """Top-to-bottom CJK column centred on x, first glyph's em-box top at y. Returns (d, height)."""
    tt, font, upem = _load(name, tuple(sorted(axes)))
    gs = tt.getGlyphSet(); cmap = tt.getBestCmap(); hmtx = tt["hmtx"]
    k = size / upem
    asc = 0.88 * upem  # CJK ideographic em box: ~0.88 above baseline
    parts, yy = [], y
    for ch in text:
        g = cmap[ord(ch)]
        adv = hmtx[g][0] * k
        sp = SVGPathPen(gs, _fmt)
        gs[g].draw(TransformPen(sp, (k, 0, 0, -k, x - adv / 2, yy + asc * k)))
        parts.append(sp.getCommands())
        yy += size * (1 + gap)
    return "".join(parts), yy - y - size * gap

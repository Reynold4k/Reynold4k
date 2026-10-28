"""Write assets/mobius-ant-{dark,light}.svg: python src/build.py"""
import pathlib
import numpy as np
import glyphs, model
from model import TAU, P, Scene, Occluder, strip_layers, membrane, ant_pose, smoothstep

THEMES = {
    "dark": dict(ink="#E6EDF3", accent="#FF5A36",
                 rule_vis=(0.10, 0.40), rule_hid=(0.035, 0.07),
                 edge_vis=(0.45, 0.95), edge_hid=(0.08, 0.16),
                 fill=(0.0, 0.10), ghost=0.38, trail_dim=0.28, text=0.80, text_dim=0.50, glow=0.9),
    "light": dict(ink="#1F2328", accent="#D93A1A",
                  rule_vis=(0.10, 0.42), rule_hid=(0.035, 0.075),
                  edge_vis=(0.50, 0.95), edge_hid=(0.08, 0.16),
                  fill=(0.0, 0.07), ghost=0.30, trail_dim=0.28, text=0.85, text_dim=0.56, glow=0.7),
}

MONO = ("GeistMono[wght].ttf", (("wght", 300),))
CJK = ("NotoSerifSC[wght].ttf", (("wght", 300),))
ITAL = ("EBGaramond-Italic[wght].ttf", (("wght", 400),))


def lerp(r, x):
    return r[0] + (r[1] - r[0]) * x


def num(v, s=10):
    """Compact number rounded to a step of 1/s (s=2 -> 0.5, s=10 -> 0.1)."""
    r = round(v * s) / s
    if r == int(r):
        return str(int(r))
    t = f"{r:.3f}".rstrip("0").rstrip(".")
    return t.replace("0.", ".", 1) if t.startswith(("0.", "-0.")) else t


def poly(xy, s=2):
    """Polyline with relative steps taken between *rounded* absolute points, so no drift accumulates."""
    q = np.round(np.asarray(xy) * s) / s
    out = f"M{num(q[0][0], s)} {num(q[0][1], s)}"
    for a, b in zip(q[:-1], q[1:]):
        out += f"l{num(b[0] - a[0], s)} {num(b[1] - a[1], s)}"
    return out.replace(" -", "-")


def unwrap180(th):
    out = [th[0]]
    for t in th[1:]:
        k = np.round((out[-1] - t) / 180.0)
        out.append(t + 180.0 * k)
    return out


def flash(base, hot, times, T, hold=1.1):
    """SMIL colour animation: `base`, jumping to `hot` at each time in `times` and fading back over `hold` s."""
    pts = [(0.0, base)]
    for t in times:
        pts += [(max(t - 0.02, 0) / T, base), (t / T, hot), (min(t + hold, T - 0.001) / T, base)]
    pts += [(1.0, base)]
    pts = sorted(set(pts))
    return (f'<animate attributeName="fill" dur="{T:g}s" repeatCount="indefinite" calcMode="linear" '
            f'values="{";".join(v for _, v in pts)}" keyTimes="{";".join(num(k, 100000) for k, _ in pts)}"/>')


def formula(th, P, x0, y0, size=26, lead=42, anchor="start"):
    """Two lines: the quotient that defines the strip, and the ant's live point in it.
    Digits are odometer wheels that jump once per step of the ant (SMIL, calcMode=discrete)."""
    ink, acc = th["ink"], th["accent"]
    T = P["T"]
    adv = glyphs.advance("0", MONO[0], size, MONO[1])
    line1 = "M = [0,1]² / (0,y) ~ (1,1−y)"
    line2 = "(x, y) = (0.###, 0.#00)"
    if anchor == "middle":
        x1, x2 = x0 - len(line1) * adv / 2, x0 - len(line2) * adv / 2
    else:
        x1 = x2 = x0
    defs, out = [], []
    # line 1, with the identification flashing whenever the ant crosses the seam
    cut = line1.index("(0,y)")
    d, _ = glyphs.text_path(line1[:cut], MONO[0], size, x1, y0, axes=MONO[1])
    out.append(f'<path fill="{ink}" fill-opacity="{th["text"]}" d="{d}"/>')
    d, _ = glyphs.text_path(line1[cut:], MONO[0], size, x1 + cut * adv, y0, axes=MONO[1])
    out.append(f'<path fill="{ink}" fill-opacity="{th["text"]}" d="{d}">{flash(ink, acc, model.seam_times(P), T)}</path>')
    # line 2: static characters + wheels
    y2 = y0 + lead
    static = "".join(glyphs.text_path(ch, MONO[0], size, x2 + i * adv, y2, axes=MONO[1])[0]
                     for i, ch in enumerate(line2) if ch not in "# ")
    out.append(f'<path fill="{ink}" fill-opacity="{th["text_dim"]}" d="{static}"/>')
    for k in range(10):
        defs.append(f'<path id="dg{k}" d="{glyphs.text_path(str(k), MONO[0], size, 0, 0, axes=MONO[1])[0]}"/>')
    n_steps = int(round(2 * P["stride_hz"] * T))
    ts = np.arange(n_steps) * T / n_steps
    xs, ys = model.chart(ts, P)
    digits = [[int(f"{x:.3f}"[2 + j]) for x in np.minimum(xs, 0.9994)] for j in range(3)] + [[int(round(y * 10)) for y in ys]]
    slots = [i for i, ch in enumerate(line2) if ch == "#"]
    LH = 1.5 * size
    for wid, (i, seq) in enumerate(zip(slots, digits)):
        x = x2 + i * adv
        defs.append(f'<clipPath id="w{wid}"><rect x="{num(x - 1, 10)}" y="{num(y2 - 0.95 * size, 10)}" width="{num(adv + 2, 10)}" height="{num(1.25 * size, 10)}"/></clipPath>')
        keep = [0] + [k for k in range(1, n_steps) if seq[k] != seq[k - 1]]
        vals = ";".join(f"{num(x, 10)},{num(y2 - seq[k] * LH, 10)}" for k in keep)
        kts = ";".join(num(k / n_steps, 100000) for k in keep)
        stack = "".join(f'<use href="#dg{k}" xlink:href="#dg{k}" y="{num(k * LH, 10)}"/>' for k in range(10))
        out.append(f'<g clip-path="url(#w{wid})"><g fill="{acc}" transform="translate({num(x, 10)} {num(y2 - seq[0] * LH, 10)})">'
                   f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" dur="{T:g}s" repeatCount="indefinite" values="{vals}" keyTimes="{kts}"/>'
                   f'{stack}</g></g>')
    return defs, out


def text_layer(th, P):
    defs, out = [], []
    ink, acc = th["ink"], th["accent"]
    Tx = lambda d, o, extra="": out.append(f'<path fill="{ink}" fill-opacity="{o}"{extra} d="{d}"/>')
    W, H = P["W"], P["H"]
    # right: Zhuangzi in two columns, read right to left, provenance beside, seal after the last column
    size, gap, col = 46, 0.5, 74
    xr = W - 174
    yi = 150
    d, h = glyphs.vertical_cjk("吾生也有涯", CJK[0], size, xr, yi, axes=CJK[1], gap=gap)
    Tx(d, th["text"])
    d, _ = glyphs.vertical_cjk("而知也无涯", CJK[0], size, xr - col, yi, axes=CJK[1], gap=gap)
    Tx(d, th["text"])
    d, _ = glyphs.text_path("ZHUANGZI · III", MONO[0], 15, 0, 0, axes=MONO[1], tracking=0.3)
    Tx(d, th["text_dim"], f' transform="translate({xr + 44} {yi + 4}) rotate(90)"')
    out.append(f'<rect x="{xr - col - 7}" y="{yi + h + 30}" width="14" height="14" fill="{acc}"/>')
    # translation (bottom left) and the live formula (centred under the strip) share two baselines
    base, lead = H - 104, 42
    d, _ = glyphs.text_path("My life has a limit,", ITAL[0], 30, 118, base, axes=ITAL[1]); Tx(d, th["text"])
    d, _ = glyphs.text_path("but knowledge has none.", ITAL[0], 30, 118, base + lead, axes=ITAL[1]); Tx(d, th["text"])
    fx, fy, anchor = P["cx"], base, "middle"
    fd, fo = formula(th, P, fx, fy, size=28, lead=lead, anchor=anchor)
    return defs + fd, out + fo


def trail_track(sc, occ, P, dim_level, back=0.40, du=0.02, fps=10):
    """The ant's lane from (u0 - back lap) to (u0 + 2 laps) as a polyline, its browser arc length, and the
    dash-offset / dimming animations that keep the trail's head on the ant."""
    S, T, d = sc.S, P["T"], P["direction"]
    u0 = np.pi * P["u0_pi"]
    us = u0 + d * np.arange(-back * TAU, 2 * TAU + 1e-9, du)
    c = np.full_like(us, P["lane"] * S.w)
    xy, z = sc.proj(S.point(us, c))
    q = np.round(xy * 2) / 2                                  # exactly what poly() writes
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
    lap = s[np.searchsorted(us * d, (u0 + d * TAU) * d)] - s[np.searchsorted(us * d, u0 * d)]
    Lmax = 0.36 * lap
    facing = (S.surface_normal(us, c) * sc.C.view_dir(S.point(us, c))).sum(-1) > 0
    bright = facing & ~occ.hidden(xy, z, us % TAU)
    K = int(T * fps)
    ts = np.arange(K + 1) * T / K
    i_ant = (d * (model.ant_u(ts, P) - u0) + back * TAU) / du
    s_ant = np.interp(i_ant, np.arange(len(s)), s)
    off = Lmax - s_ant
    # trail brightness = opacity-weighted share of its samples on the visible face
    w_prof = lambda x: np.interp(x, [0, .1, .2, .32, .45, .6, .78, 1.0], [.94, .89, .81, .64, .49, .32, .15, 0])
    dim = []
    for sa in s_ant:
        m = (s <= sa) & (s >= sa - Lmax)
        w = w_prof((sa - s[m]) / Lmax)
        frac = (w * bright[m]).sum() / max(w.sum(), 1e-9)
        dim.append(frac + (1 - frac) * dim_level)
    dim = np.array(dim)
    vals = ";".join(num(v, 10) for v in off)
    anim = f'<animate attributeName="stroke-dashoffset" dur="{T:g}s" repeatCount="indefinite" values="{vals}"/>'
    dv = [f"{v:.2f}" for v in dim]
    keep = [0] + [i for i in range(1, K) if not (dv[i] == dv[i - 1] == dv[i + 1])] + [K]
    dim_anim = (f'<animate attributeName="opacity" dur="{T:g}s" repeatCount="indefinite" '
                f'values="{";".join(dv[i] for i in keep)}" keyTimes="{";".join(num(i / K, 10000) for i in keep)}"/>')
    return dict(xy=xy, s=s, Lmax=Lmax, off=off, anim=anim, dim_anim=dim_anim, dim0=dv[0])


def build(theme, P):
    th = THEMES[theme]
    sc = Scene(P); occ = Occluder(sc)
    W, H, T = P["W"], P["H"], P["T"]
    out = []
    A = out.append
    A(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" fill="none" role="img" aria-labelledby="t d">')
    A('<title id="t">An ant running forever on a Möbius strip</title>')
    A('<desc id="d">An ant walks a Möbius strip. After one lap it is on the other face; after two it is home. Its point in the quotient [0,1]² / (0,y) ~ (1,1−y) is shown live. 吾生也有涯，而知也无涯: my life has a limit, but knowledge has none (Zhuangzi, 3).</desc>')
    A('<defs><filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6"/></filter></defs>')

    # membrane (fresnel fill)
    A(f'<g fill="{th["ink"]}">')
    for xy, fr in membrane(sc, P["n_rulings"]):
        o = lerp(th["fill"], fr ** 2.2)
        if o >= 0.004:
            A(f'<path fill-opacity="{o:.3f}" d="M{num(xy[0,0],2)} {num(xy[0,1],2)}L{num(xy[1,0],2)} {num(xy[1,1],2)} {num(xy[2,0],2)} {num(xy[2,1],2)} {num(xy[3,0],2)} {num(xy[3,1],2)}z"/>')
    A("</g>")

    # rulings + edge: hidden first, then visible; grouped by quantised opacity
    layers = strip_layers(sc, occ, P["n_rulings"])
    for hidden in (True, False):
        for kind, width in (("rule", 1.0), ("edge", 1.7)):
            rng = th[f"{kind}_{'hid' if hidden else 'vis'}"]
            buckets = {}
            for k, h, nz, pts, _u in layers:
                if k == kind and h == hidden:
                    q = round(lerp(rng, nz ** 1.3) * 60) / 60
                    buckets.setdefault(q, []).append(np.vstack([pts[:-1:2], pts[-1:]]) if kind == "edge" and len(pts) > 4 else pts)
            for o, runs in sorted(buckets.items()):
                d = "".join(poly(r) for r in runs)
                A(f'<path stroke="{th["ink"]}" stroke-opacity="{o:.3f}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')

    # the seam where the strip is glued (x = 0 ~ 1 in the chart); it flashes when the ant crosses it
    seam = [(h, pts) for h, pts in model.seam_runs(sc, occ, P)]
    st = model.seam_times(P)
    for h, pts in seam:
        o = 0.22 if h else 0.75
        A(f'<path fill="none" stroke="{th["ink"]}" stroke-opacity="{o}" stroke-width="1.4" stroke-dasharray="5 6" d="{poly(pts)}">'
          + flash(th["ink"], th["accent"], st, T).replace('attributeName="fill"', 'attributeName="stroke"') + "</path>")

    # trail + wake: one centre-line track, dashed so that only the stretch just behind the ant is drawn;
    # a single SMIL stroke-dashoffset animation (inherited) drives every layer.
    tr = trail_track(sc, occ, P, th["trail_dim"])
    G = tr["s"][-1] + tr["Lmax"] + 50
    A('<defs>' + f'<path id="trk" d="{poly(tr["xy"])}"/>')
    A(f'<mask id="wake" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
      f'<g fill="none" stroke="#fff" stroke-dashoffset="{num(tr["off"][0], 10)}">{tr["anim"]}')
    for frac, width, alpha in ((0.07, 230, 0.55), (0.16, 230, 0.4), (0.30, 230, 0.28)):
        L = frac * tr["Lmax"]
        A(f'<use href="#trk" xlink:href="#trk" stroke-width="{width}" stroke-opacity="{alpha}" stroke-dasharray="0 {num(tr["Lmax"] - L, 10)} {num(L, 10)} {num(G, 1)}"/>')
    A("</g></mask></defs>")
    vis_rules = [pts for k, h, nz, pts, u in layers if k == "rule" and not h]
    A(f'<path mask="url(#wake)" stroke="{th["ink"]}" stroke-opacity="{th["glow"]}" stroke-width="1.3" stroke-linecap="round" d="{"".join(poly(r) for r in vis_rules)}"/>')
    A(f'<g fill="none" stroke="{th["accent"]}" stroke-linecap="butt" stroke-linejoin="round" stroke-dashoffset="{num(tr["off"][0], 10)}" opacity="{tr["dim0"]}">{tr["anim"]}{tr["dim_anim"]}')
    for frac, width, alpha in ((0.10, 2.6, .45), (0.20, 2.2, .40), (0.32, 1.8, .35), (0.45, 1.5, .30), (0.60, 1.2, .25), (0.78, 0.9, .20), (1.0, 0.7, .15)):
        L = frac * tr["Lmax"]
        A(f'<use href="#trk" xlink:href="#trk" stroke-width="{width}" stroke-opacity="{alpha}" stroke-dasharray="0 {num(tr["Lmax"] - L, 10)} {num(L, 10)} {num(G, 1)}"/>')
    A("</g>")

    # ant
    Kb = int(round(T * P["fps_body"]))
    Kl = int(round(T * P["fps_limbs"]))
    poses_l = [ant_pose(sc, occ, k * T / Kl, P) for k in range(Kl)]
    step = max(Kl // Kb, 1)
    poses_b = poses_l[::step]

    def anim(attr, vals):
        return f'<animate attributeName="{attr}" dur="{T:g}s" repeatCount="indefinite" values="{";".join(vals + [vals[0]])}"/>'

    A('<g id="ant">')
    for i in range(len(model.BODY)):
        e = np.array([p["ells"][i] for p in poses_b])
        theta = unwrap180(list(e[:, 4]))
        cx = [num(v, 10) for v in e[:, 0]]; cy = [num(v, 10) for v in e[:, 1]]
        rx = [num(v, 10) for v in e[:, 2]]; ry = [num(v, 10) for v in e[:, 3]]
        tl = [f"{a},{b}" for a, b in zip(cx, cy)]
        rt = [num(v, 10) for v in theta]
        # close the loop on the turn equivalent to the first angle (an ellipse is symmetric under 180 deg)
        rt_close = rt + [num(theta[0] + 180.0 * np.round((theta[-1] - theta[0]) / 180.0), 10)]
        A(f'<ellipse rx="{rx[0]}" ry="{ry[0]}" transform="translate({tl[0]}) rotate({rt[0]})">'
          + anim("rx", rx) + anim("ry", ry)
          + f'<animateTransform attributeName="transform" type="translate" dur="{T:g}s" repeatCount="indefinite" values="{";".join(tl + [tl[0]])}"/>'
          + f'<animateTransform attributeName="transform" type="rotate" additive="sum" dur="{T:g}s" repeatCount="indefinite" values="{";".join(rt_close)}"/>'
          + "</ellipse>")
    legs = ["".join(poly(l) for l in p["legs"]) for p in poses_l]
    ants = ["".join(poly(a) for a in p["ants"]) for p in poses_l]
    A(f'<path fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" d="{legs[0]}">{anim("d", legs)}</path>')
    A(f'<path fill="none" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" d="{ants[0]}">{anim("d", ants)}</path>')
    A("</g>")

    # solid copy shows only while the ant's face looks at the camera and nothing is in front of it;
    # flickers shorter than 0.8 s are dropped, then the cross-fades are softened (the signal is periodic)
    vis = np.array([smoothstep(-0.07, 0.07, p["facing"]) * (1 - p["hidden"]) for p in poses_l])
    K = len(vis)
    on = vis > 0.5
    min_run = int(0.8 * P["fps_limbs"])
    i0 = int(np.argmin(on)) if not on.all() else 0   # start scanning from an 'off' frame
    idx = (np.arange(K) + i0) % K
    run = []
    for j in list(idx) + [idx[0]]:
        if on[j]:
            run.append(j)
        else:
            if 0 < len(run) < min_run:
                vis[run] = 0.0
            run = []
    ker = np.ones(5) / 5
    vis = np.convolve(np.r_[vis[-2:], vis, vis[:2]], ker, mode="valid")
    vals = [f"{v:.2f}".rstrip("0").rstrip(".") for v in vis] + [f"{vis[0]:.2f}".rstrip("0").rstrip(".")]
    keep = [0] + [i for i in range(1, K) if not (vals[i] == vals[i - 1] == vals[i + 1])] + [K]
    vt = ";".join(vals[i] for i in keep)
    kts = ";".join(num(i / K, 100000) for i in keep)
    A(f'<use href="#ant" xlink:href="#ant" fill="{th["accent"]}" stroke="{th["accent"]}" opacity="{th["ghost"]}" filter="url(#blur)"/>')
    A(f'<use href="#ant" xlink:href="#ant" fill="{th["accent"]}" stroke="{th["accent"]}" opacity="{vals[0]}">'
      + f'<animate attributeName="opacity" dur="{T:g}s" repeatCount="indefinite" values="{vt}" keyTimes="{kts}"/>' + "</use>")

    tdefs, tout = text_layer(th, P)
    out += ["<defs>" + "".join(tdefs) + "</defs>"] + tout
    A("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=str(pathlib.Path(__file__).resolve().parent.parent / "assets"))
    ap.add_argument("--set", default="{}", help="JSON overrides for model.P")
    a = ap.parse_args()
    PP = dict(P, **json.loads(a.set))
    for theme in THEMES:
        svg = build(theme, PP)
        f = pathlib.Path(a.outdir) / f"mobius-ant-{theme}.svg"
        f.write_text(svg, encoding="utf-8")
        print(f, len(svg.encode()) // 1024, "KB")

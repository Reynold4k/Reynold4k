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


def text_layer(th):
    out = []
    ink, acc = th["ink"], th["accent"]
    T = lambda d, o, extra="": out.append(f'<path fill="{ink}" fill-opacity="{o}"{extra} d="{d}"/>')
    # right: vertical inscription with provenance and a seal
    size, gap = 46, 0.5
    xi, yi = 1426, 160
    d, h = glyphs.vertical_cjk("周行而不殆", CJK[0], size, xi, yi, axes=CJK[1], gap=gap)
    T(d, th["text"])
    d, w = glyphs.text_path("LAOZI · XXV", MONO[0], 15, 0, 0, axes=MONO[1], tracking=0.3)
    T(d, th["text_dim"], f' transform="translate({xi + 44} {yi + 4}) rotate(90)"')
    out.append(f'<rect x="{xi - 7}" y="{yi + h + 30}" width="14" height="14" fill="{acc}"/>')
    # left: translation + definition
    x0, y0 = 118, 438
    d, w = glyphs.text_path("It goes round and round,", ITAL[0], 30, x0, y0, axes=ITAL[1])
    T(d, th["text"])
    d, w = glyphs.text_path("and never tires.", ITAL[0], 30, x0, y0 + 38, axes=ITAL[1])
    T(d, th["text"])
    d, w = glyphs.text_path("M = [0,1] × [0,1] / (0,y) ~ (1,1−y)", MONO[0], 16.5, x0, y0 + 88, axes=MONO[1], tracking=0.02)
    T(d, th["text_dim"])
    return out


def trail_track(sc, occ, P, dim_level, back=0.40, du=0.02, fps=10):
    """Centre-line polyline from (u0 - back lap) to (u0 + 2 laps), its browser arc length, and the
    dash-offset / dimming animations that keep the trail's head on the ant."""
    S, T, d = sc.S, P["T"], P["direction"]
    u0 = np.pi * P["u0_pi"]
    us = u0 + d * np.arange(-back * TAU, 2 * TAU + 1e-9, du)
    xy, z = sc.proj(S.center(us))
    q = np.round(xy * 2) / 2                                  # exactly what poly() writes
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
    lap = s[np.searchsorted(us * d, (u0 + d * TAU) * d)] - s[np.searchsorted(us * d, u0 * d)]
    Lmax = 0.36 * lap
    facing = (S.normal(us) * sc.C.view_dir(S.center(us))).sum(-1) > 0
    bright = facing & ~occ.hidden(xy, z, us % TAU)
    K = int(T * fps)
    ts = np.arange(K + 1) * T / K
    i_ant = (back * TAU + 4 * np.pi * ts / T) / du
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
    A('<desc id="d">A single ant walks the centre line of a Möbius strip. After one lap it is on the other face; after two it is home. 周行而不殆: it goes round and round, and never tires (Laozi, 25).</desc>')
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

    out += text_layer(th)
    A("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    assets = pathlib.Path(__file__).resolve().parent.parent / "assets"
    for theme in THEMES:
        svg = build(theme, P)
        f = assets / f"mobius-ant-{theme}.svg"
        f.write_text(svg, encoding="utf-8")
        print(f, len(svg.encode()) // 1024, "KB")

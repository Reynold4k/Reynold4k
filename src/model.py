"""Scene model: the strip, what hides what, and the walking ant (all in canvas coordinates)."""
import functools
import numpy as np, shapely
from geom import Strip, Camera

TAU = 2 * np.pi

# Camera, strip, canvas and motion. T is one full cycle = two laps (the ant is home again).
P = dict(
    el=26.0, az=-90.0, dist=6.0, phi_deg=135.0, w=0.42,
    W=1600, H=720, strip_h=450, cx=800, cy=300,
    n_rulings=150, T=20.0, fps_body=10, fps_limbs=20, stride_hz=4.0, antenna_hz=1.25,
    ant_len=0.25, direction=1, u0_pi=1.5,
    lane=-0.2,      # the ant's lateral position, as a fraction of the half-width (0 = centre line)
    seam_pi=1.7,    # where the strip is glued: x = 0 ~ 1 in the quotient chart
)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Scene:
    def __init__(self, P):
        self.P = P
        self.S = Strip(P["w"], np.radians(P["phi_deg"]))
        self.C = Camera(el=P["el"], az=P["az"], dist=P["dist"])
        ue = np.linspace(0, 2 * TAU, 4000)
        e, _ = self.C.project(self.S.point(ue, self.S.w))
        lo, hi = e.min(0), e.max(0)
        self.k = P["strip_h"] / (hi[1] - lo[1])
        self.off = np.array([P["cx"], P["cy"]]) - self.k * (lo + hi) / 2
        _, zz = self.C.project(self.S.point(ue, self.S.w))
        self.zmin, self.zmax = zz.min(), zz.max()

    def proj(self, p):
        xy, z = self.C.project(p)
        return xy * self.k + self.off, z

    def near(self, z):  # 1 = nearest, 0 = farthest
        return np.clip((self.zmax - z) / (self.zmax - self.zmin), 0, 1)


class Occluder:
    """Static strip as a mesh of small quads; answers 'is this 3-D point hidden by another part?'"""

    def __init__(self, sc, nu=480, nv=8):
        S = sc.S
        u = np.linspace(0, TAU, nu + 1); v = np.linspace(-S.w, S.w, nv + 1)
        U, V = np.meshgrid(u, v, indexing="ij")
        xy, z = sc.proj(S.point(U, V))
        qxy, qz, qu = [], [], []
        for i in range(nu):
            for j in range(nv):
                idx = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                qxy.append([xy[a, b] for a, b in idx]); qz.append([z[a, b] for a, b in idx])
                qu.append((u[i] + u[i + 1]) / 2)
        self.qxy, self.qz, self.qu = np.array(qxy), np.array(qz), np.array(qu)
        boxes = shapely.box(self.qxy[..., 0].min(1), self.qxy[..., 1].min(1), self.qxy[..., 0].max(1), self.qxy[..., 1].max(1))
        self.tree = shapely.STRtree(boxes)

    @staticmethod
    def _bary(p, a, b, c):
        v0, v1, v2 = b - a, c - a, p - a
        d00 = (v0 * v0).sum(-1); d01 = (v0 * v1).sum(-1); d11 = (v1 * v1).sum(-1)
        d20 = (v2 * v0).sum(-1); d21 = (v2 * v1).sum(-1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1)
        be = (d11 * d20 - d01 * d21) / den; ga = (d00 * d21 - d01 * d20) / den
        al = 1 - be - ga
        inside = ok & (al >= -1e-6) & (be >= -1e-6) & (ga >= -1e-6)
        return inside, al, be, ga

    def hidden(self, xy, z, u, delta=0.32, eps=0.004):
        xy = np.asarray(xy).reshape(-1, 2); z = np.asarray(z).ravel(); u = np.broadcast_to(u, z.shape).ravel()
        pi, qi = self.tree.query(shapely.points(xy), predicate="intersects")
        p = xy[pi]; Q = self.qxy[qi]; Z = self.qz[qi]
        zq = np.full(len(pi), np.inf)
        for tri in ((0, 1, 2), (0, 2, 3)):
            ins, al, be, ga = self._bary(p, Q[:, tri[0]], Q[:, tri[1]], Q[:, tri[2]])
            zt = al * Z[:, tri[0]] + be * Z[:, tri[1]] + ga * Z[:, tri[2]]
            zq = np.where(ins, np.minimum(zq, zt), zq)
        du = np.abs((u[pi] - self.qu[qi] + np.pi) % TAU - np.pi)
        occ = (du > delta) & (zq < z[pi] - eps)
        out = np.zeros(len(z), bool); out[pi[occ]] = True
        return out


# ----------------------------------------------------------------------------- strip

def strip_layers(sc, occ, n):
    """Rulings + single edge, each split into visible / hidden runs with a depth value."""
    S = sc.S
    out = []  # (kind, hidden, nearness, points)
    u = np.arange(n) * TAU / n
    v = np.linspace(-S.w, S.w, 61)
    for ui in u:
        pts3 = S.point(np.full_like(v, ui), v)
        xy, z = sc.proj(pts3)
        hid = occ.hidden(xy, z, ui)
        cuts = np.flatnonzero(np.diff(hid.astype(int))) + 1
        bounds = [0, *cuts, len(v)]
        for a, b in zip(bounds[:-1], bounds[1:]):
            ia, ib = max(a - 0.5, 0), min(b - 0.5, len(v) - 1)
            pa = xy[0] + (xy[-1] - xy[0]) * ia / (len(v) - 1)
            pb = xy[0] + (xy[-1] - xy[0]) * ib / (len(v) - 1)
            out.append(("rule", bool(hid[a]), float(sc.near(z[a:b]).mean()), np.array([pa, pb]), float(ui)))
    ue = np.linspace(0, 2 * TAU, 2401)
    xy, z = sc.proj(S.point(ue, S.w))
    hid = occ.hidden(xy, z, ue)
    nz = sc.near(z)
    lvl = np.round(nz * 6).astype(int)
    key = hid.astype(int) * 100 + lvl
    cuts = np.flatnonzero(np.diff(key)) + 1
    bounds = [0, *cuts, len(ue) - 1]
    for a, b in zip(bounds[:-1], bounds[1:]):
        out.append(("edge", bool(hid[a]), float(nz[a:b + 1].mean()), xy[a:b + 1], None))
    return out


def seam_runs(sc, occ, P):
    """The ruling at the seam, split into visible / hidden runs."""
    S, u = sc.S, np.pi * P["seam_pi"]
    v = np.linspace(-S.w, S.w, 61)
    xy, z = sc.proj(S.point(np.full_like(v, u), v))
    hid = occ.hidden(xy, z, u)
    cuts = np.flatnonzero(np.diff(hid.astype(int))) + 1
    bounds = [0, *cuts, len(v)]
    return [(bool(hid[a]), xy[max(a - 1, 0):b]) for a, b in zip(bounds[:-1], bounds[1:])]


def membrane(sc, n):
    S, C = sc.S, sc.C
    u = np.arange(n) * TAU / n
    quads = []
    for i, ui in enumerate(u):
        uj = ui + TAU / n
        pts = [S.point(ui, -S.w), S.point(ui, S.w), S.point(uj, S.w), S.point(uj, -S.w)]
        xy, _ = sc.proj(np.array(pts))
        fres = []
        for vv in np.linspace(-S.w, S.w, 5):
            pc = S.point(np.array(ui + TAU / n / 2), np.array(vv))
            nrm = S.surface_normal(np.array(ui + TAU / n / 2), np.array(vv))
            fres.append(1 - abs(float(np.dot(nrm, C.view_dir(pc)))))
        quads.append((xy, float(np.mean(fres))))
    return quads


# ----------------------------------------------------------------------------- ant

BODY = [  # local centre (x fwd, y left, z up) and radii, in body lengths
    ((0.315, 0.0, 0.110), (0.072, 0.062, 0.050)),   # head
    ((0.150, 0.0, 0.120), (0.112, 0.042, 0.046)),   # mesosoma
    ((-0.015, 0.0, 0.125), (0.026, 0.022, 0.036)),  # petiole node
    ((-0.205, 0.0, 0.135), (0.160, 0.100, 0.088)),  # gaster
]
COXA = [(0.205, 0.026, 0.095), (0.150, 0.030, 0.090), (0.095, 0.030, 0.095)]
FOOT = [(0.500, 0.230, 0.0), (0.140, 0.360, 0.0), (-0.300, 0.330, 0.0)]
TRIPOD_A = {(+1, 0), (-1, 1), (+1, 2)}


def ant_local(t, P):
    """Leg + antenna polylines in local coords at time t (seconds)."""
    v_bl = lane_table(P)[1][-1] / P["T"] / P["ant_len"]   # body lengths / s
    f = P["stride_hz"]; duty = 0.56
    stride = v_bl / f * duty
    legs = []
    for side in (+1, -1):
        for k in range(3):
            ph = (f * t + (0.0 if (side, k) in TRIPOD_A else 0.5) + 0.07 * k) % 1.0
            if ph < duty:
                dx, lift = stride * (0.5 - ph / duty), 0.0
            else:
                q = (ph - duty) / (1 - duty)
                q = q * q * (3 - 2 * q)
                dx, lift = stride * (-0.5 + q), 0.075 * np.sin(np.pi * (ph - duty) / (1 - duty))
            cx, cy, cz = COXA[k]; fx, fy, fz = FOOT[k]
            coxa = np.array([cx, side * cy, cz])
            foot = np.array([fx + dx, side * fy, fz + lift])
            knee = coxa + 0.42 * (foot - coxa)
            knee[1] += side * 0.035; knee[2] = 0.215 + 0.6 * lift
            legs.append(np.array([coxa, knee, foot]))
    ants = []
    for side in (+1, -1):
        sw = 0.22 * np.sin(TAU * P["antenna_hz"] * t + (0.0 if side > 0 else 2.1))
        base = np.array([0.375, side * 0.028, 0.130])
        elbow = base + np.array([0.035, side * 0.080, 0.075])
        d = np.array([0.190, side * 0.050, -0.050])
        c, s = np.cos(sw * side), np.sin(sw * side)
        d = np.array([c * d[0] - s * d[1], s * d[0] + c * d[1], d[2]])
        ants.append(np.array([base, elbow, elbow + d]))
    bob = 0.006 * np.sin(2 * TAU * f * t)
    return legs, ants, bob


@functools.lru_cache(None)
def _lane_table(w, phi_deg, u0_pi, direction, lane):
    """Parameter u and arc length s along the ant's lane over one full cycle (two laps)."""
    S = Strip(w, np.radians(phi_deg))
    us = np.pi * u0_pi + direction * np.linspace(0, 2 * TAU, 8001)
    pts = S.point(us, np.full_like(us, lane * w))
    return us, np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]


def lane_table(P):
    return _lane_table(P["w"], P["phi_deg"], P["u0_pi"], P["direction"], P["lane"])


def ant_u(t, P):
    """Strip parameter of the ant at time t; it walks its lane at constant speed, two laps per period."""
    us, s = lane_table(P)
    n = np.floor(np.asarray(t, float) / P["T"])
    frac = np.asarray(t, float) / P["T"] - n
    return np.interp(frac * s[-1], s, us) + n * P["direction"] * 2 * TAU


def chart(t, P):
    """The ant's point (x, y) in the quotient chart [0,1] x [0,1] / (0,y) ~ (1,1-y), cut at the seam."""
    a = P["direction"] * (ant_u(t, P) - np.pi * P["seam_pi"])
    k = np.floor(a / TAU)
    x = a / TAU - k
    y = ((-1.0) ** k * P["lane"] + 1) / 2
    return x, y


def seam_times(P):
    """Times in [0, T) at which the ant crosses the seam."""
    us, s = lane_table(P)
    d = P["direction"]
    out = []
    for k in range(-2, 4):
        uc = np.pi * P["seam_pi"] + k * TAU
        if (us[0] - uc) * (us[-1] - uc) < 0:
            out.append(float(np.interp(uc * d, us * d, s) / s[-1] * P["T"]))
    return sorted(t % P["T"] for t in out)


def ant_frame(sc, u, P):
    S = sc.S
    c, h = P["lane"] * S.w, 1e-5
    O = S.point(np.array(u), np.array(c))
    T = P["direction"] * (S.point(np.array(u + h), np.array(c)) - S.point(np.array(u - h), np.array(c)))
    T /= np.linalg.norm(T)
    N = S.surface_normal(np.array(u), np.array(c))
    B = np.cross(N, T)
    return O, np.stack([T, B, N], 1)  # R: columns = local axes in world


def ant_pose(sc, occ, t, P):
    """Projected ant at time t: body ellipses (cx, cy, rx, ry, theta_deg), limb polylines, visibility."""
    u = ant_u(t, P)
    O, R = ant_frame(sc, u, P)
    L = P["ant_len"]
    legs, ants, bob = ant_local(t, P)
    W = lambda q: O + R @ (np.asarray(q) * L)
    ells, centers = [], []
    for (c, r) in BODY:
        cw = W(np.array(c) + [0, 0, bob]); centers.append(cw)
        h = 1e-4
        J = np.stack([(sc.proj(cw + h * e)[0] - sc.proj(cw - h * e)[0]) / (2 * h) for e in np.eye(3)], 1)
        M = J @ (R @ np.diag(np.array(r) * L))
        lam, vec = np.linalg.eigh(M @ M.T)          # ascending
        e1 = vec[:, 1]
        cxy = sc.proj(cw)[0]
        ells.append((cxy[0], cxy[1], np.sqrt(lam[1]), np.sqrt(max(lam[0], 0)), np.degrees(np.arctan2(e1[1], e1[0]))))
    limbs_l = [sc.proj(np.array([W(pt) for pt in leg]))[0] for leg in legs]
    limbs_a = [sc.proj(np.array([W(pt + np.array([0, 0, bob])) for pt in a]))[0] for a in ants]
    N = R[:, 2]
    facing = float(np.dot(N, sc.C.view_dir(O)))
    probe = centers + [W(leg[2]) for leg in legs] + [W(a[2]) for a in ants]   # body, feet, antenna tips
    cxy, cz = sc.proj(np.array(probe))
    hid = occ.hidden(cxy, cz, np.full(len(cz), u % TAU))
    return dict(ells=ells, legs=limbs_l, ants=limbs_a, facing=facing, hidden=float(hid.mean()))

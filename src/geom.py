"""Möbius strip geometry + pinhole camera. Units: strip radius R = 1."""
import numpy as np

class Strip:
    def __init__(self, w=0.38, phi=0.0):
        self.w, self.phi = w, phi
    def alpha(self, u):            # twist angle of the ruling
        return u / 2 + self.phi
    def center(self, u):
        return np.stack([np.cos(u), np.sin(u), np.zeros_like(u)], -1)
    def ruling(self, u):           # unit ruling direction d(u)
        a = self.alpha(u)
        er = np.stack([np.cos(u), np.sin(u), np.zeros_like(u)], -1)
        ez = np.array([0.0, 0.0, 1.0])
        return np.cos(a)[..., None] * er + np.sin(a)[..., None] * ez
    def point(self, u, v):
        return self.center(u) + np.asarray(v)[..., None] * self.ruling(u)
    def tangent(self, u):          # unit centre-line tangent e_theta
        return np.stack([-np.sin(u), np.cos(u), np.zeros_like(u)], -1)
    def normal(self, u):           # continuous along u; flips after 2*pi
        a = self.alpha(u)
        er = np.stack([np.cos(u), np.sin(u), np.zeros_like(u)], -1)
        ez = np.array([0.0, 0.0, 1.0])
        return np.cos(a)[..., None] * ez - np.sin(a)[..., None] * er
    def surface_normal(self, u, v):  # exact normal at (u, v), same orientation as normal(u) at v=0
        e = 1e-5
        du = (self.point(u + e, v) - self.point(u - e, v)) / (2 * e)
        dv = self.ruling(u)
        n = np.cross(du, dv)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        s = np.sign(np.sum(n * self.normal(u), -1))
        return n * s[..., None]

class Camera:
    """Pinhole camera looking at `target` from elevation/azimuth (deg) at distance `dist`."""
    def __init__(self, el=32, az=-62, dist=6.0, focal=1.0, roll=0.0, target=(0, 0, 0)):
        el, az, roll = np.radians([el, az, roll])
        self.target = np.array(target, float)
        fwd = -np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
        self.eye = self.target - dist * fwd
        right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        c, s = np.cos(roll), np.sin(roll)
        self.right, self.up = c * right + s * up, -s * right + c * up
        self.fwd, self.dist, self.focal = fwd, dist, focal
    def view_dir(self, p):           # unit vector from point toward the eye
        d = self.eye - p
        return d / np.linalg.norm(d, axis=-1, keepdims=True)
    def project(self, p):
        """Return (x, y, depth); x right, y down (SVG), in units of the image plane at focal*dist."""
        q = p - self.eye
        z = q @ self.fwd
        x = (q @ self.right) / z * self.dist * self.focal
        y = -(q @ self.up) / z * self.dist * self.focal
        return np.stack([x, y], -1), z

"""Pure-Python 3D geometry utilities (no Rhino dependency).

Vectors and points are ``(x, y, z)`` tuples.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import NamedTuple

from pocketknife.geometry2d import min_bounding_rect

Vec3 = tuple[float, float, float]

ACCURACY_SAMPLES = {"Fast": 60, "Normal": 250, "Precise": 1000}


class Box3D(NamedTuple):
    """Oriented box.

    Attributes:
        center: Box center.
        axes: Three orthonormal axes (local X, Y, Z).
        sizes: Box sizes along the three axes.
    """

    center: Vec3
    axes: tuple[Vec3, Vec3, Vec3]
    sizes: Vec3

    @property
    def volume(self) -> float:
        """Box volume."""
        return self.sizes[0] * self.sizes[1] * self.sizes[2]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def _perpendicular_frame(w: Vec3) -> tuple[Vec3, Vec3]:
    helper = (1.0, 0.0, 0.0) if abs(w[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit(_cross(helper, w))
    return u, _cross(w, u)


def principal_axes(points: Sequence[Vec3]) -> list[Vec3]:
    """Returns the principal axes of a point set (Jacobi eigen-decomposition).

    Args:
        points: Input points.

    Returns:
        Three orthonormal axes.
    """
    n = len(points)
    mean = tuple(sum(p[k] for p in points) / n for k in range(3))
    cov = [[0.0] * 3 for _ in range(3)]
    for p in points:
        d = (p[0] - mean[0], p[1] - mean[1], p[2] - mean[2])
        for r in range(3):
            for c in range(3):
                cov[r][c] += d[r] * d[c]
    vecs = [[1.0 if r == c else 0.0 for c in range(3)] for r in range(3)]
    for _ in range(50):
        off = max(abs(cov[0][1]), abs(cov[0][2]), abs(cov[1][2]))
        if off < 1e-15:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(cov[p][q]) < 1e-30:
                continue
            theta = (cov[q][q] - cov[p][p]) / (2.0 * cov[p][q])
            t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1))
            c = 1.0 / math.sqrt(t * t + 1)
            s = t * c
            for k in range(3):
                akp, akq = cov[k][p], cov[k][q]
                cov[k][p], cov[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = cov[p][k], cov[q][k]
                cov[p][k], cov[q][k] = c * apk - s * aqk, s * apk + c * aqk
            for k in range(3):
                vkp, vkq = vecs[k][p], vecs[k][q]
                vecs[k][p], vecs[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    return [_unit((vecs[0][k], vecs[1][k], vecs[2][k])) for k in range(3)]


def _fibonacci_hemisphere(count: int) -> list[Vec3]:
    golden = math.pi * (3.0 - math.sqrt(5.0))
    dirs = []
    for i in range(count):
        z = 1.0 - (i + 0.5) / count  # z in (0, 1]: one hemisphere is enough.
        r = math.sqrt(max(0.0, 1.0 - z * z))
        dirs.append((r * math.cos(golden * i), r * math.sin(golden * i), z))
    return dirs


def box_for_direction(points: Sequence[Vec3], w: Vec3) -> Box3D:
    """Smallest box having one axis parallel to ``w``.

    Args:
        points: Input points.
        w: Unit direction of the box local Z axis.

    Returns:
        The box obtained from the 2D minimum rectangle of the projected points.
    """
    u0, v0 = _perpendicular_frame(w)
    rect = min_bounding_rect([(_dot(p, u0), _dot(p, v0)) for p in points])
    heights = [_dot(p, w) for p in points]
    h0, h1 = min(heights), max(heights)
    ca, sa = math.cos(rect.angle), math.sin(rect.angle)
    x_axis = tuple(ca * u0[k] + sa * v0[k] for k in range(3))
    y_axis = tuple(-sa * u0[k] + ca * v0[k] for k in range(3))
    cu, cv = rect.center
    hc = (h0 + h1) / 2.0
    center = tuple(cu * u0[k] + cv * v0[k] + hc * w[k] for k in range(3))
    return Box3D(center, (x_axis, y_axis, w), (rect.width, rect.height, h1 - h0))


def _score(box: Box3D) -> tuple[float, float]:
    a, b, c = box.sizes
    return (box.volume, a * b + b * c + a * c)


def _rotate(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    c, s = math.cos(angle), math.sin(angle)
    cr = _cross(axis, v)
    d = _dot(axis, v) * (1.0 - c)
    return _unit(tuple(v[k] * c + cr[k] * s + axis[k] * d for k in range(3)))


def min_bounding_box(points: Sequence[Vec3], accuracy: str = "Normal") -> Box3D:
    """Approximates the minimum-volume oriented bounding box.

    Candidate box Z directions (world axes, principal axes and a uniform
    sampling of the hemisphere) are each solved exactly in 2D; the best one is
    then refined with a shrinking local search.

    Args:
        points: Input points, at least one.
        accuracy: ``"Fast"``, ``"Normal"`` or ``"Precise"``.

    Returns:
        The best box found. Ties on volume (flat inputs) are broken by area.

    Raises:
        ValueError: If ``points`` is empty.
    """
    pts = list(set(points))
    if not pts:
        raise ValueError("At least one point is required.")
    samples = ACCURACY_SAMPLES.get(accuracy, ACCURACY_SAMPLES["Normal"])
    candidates: list[Vec3] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    if len(pts) >= 3:
        candidates += principal_axes(pts)
    candidates += _fibonacci_hemisphere(samples)

    best = min((box_for_direction(pts, w) for w in candidates), key=_score)
    step = math.sqrt(2.0 * math.pi / samples)
    while step > 1e-5:
        w = best.axes[2]
        a, b = _perpendicular_frame(w)
        improved = False
        for axis in (
            a,
            b,
            _unit(tuple(a[k] + b[k] for k in range(3))),
            _unit(tuple(a[k] - b[k] for k in range(3))),
        ):
            for sign in (1.0, -1.0):
                box = box_for_direction(pts, _rotate(w, axis, sign * step))
                if _score(box) < _score(best):
                    best, improved = box, True
        if not improved:
            step /= 2.0
    return best

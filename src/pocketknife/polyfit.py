"""Pure-Python rebuild of faceted curves into lines, arcs and minimal NURBS.

Exporters (Revit, SketchUp, Blender) write circles, arcs and free curves as
polylines. This module finds true corners, recognises the runs that are
exactly lines or uniformly faceted arcs, and fits the rest with cubic
B-splines of minimum control-point count, keeping every input vertex within
tolerance. No Rhino and no numpy dependency.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pocketknife.geometry3d import principal_axes

Vec3 = tuple[float, float, float]

RHYTHM_EXCESS = math.radians(5.0)
RHYTHM_RATIO = 2.0


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec3) -> Vec3:
    n = _norm(a)
    return (0.0, 0.0, 0.0) if n == 0.0 else _scale(a, 1.0 / n)


def _dist(a: Vec3, b: Vec3) -> float:
    return _norm(_sub(a, b))


def _angle(a: Vec3, b: Vec3) -> float:
    """Angle between two vectors, in radians."""
    na, nb = _norm(a), _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    c = _dot(a, b) / (na * nb)
    return math.acos(max(-1.0, min(1.0, c)))


def dedupe(points: Sequence[Vec3], closed: bool, eps: float) -> list[Vec3]:
    """Removes consecutive duplicate vertices.

    Args:
        points: Vertices.
        closed: True for a closed ring; a last vertex equal to the first is
            removed too.
        eps: Vertices closer than this are duplicates.

    Returns:
        The cleaned vertices.
    """
    out: list[Vec3] = []
    for p in points:
        p = (float(p[0]), float(p[1]), float(p[2]))
        if not out or _dist(p, out[-1]) > eps:
            out.append(p)
    if closed:
        while len(out) > 1 and _dist(out[0], out[-1]) <= eps:
            out.pop()
    return out


def turning_angles(points: Sequence[Vec3], closed: bool) -> list[float]:
    """Turning angle at every vertex.

    Args:
        points: Vertices without duplicates.
        closed: True for a closed ring.

    Returns:
        Angles in radians; the ends of an open polyline get 0.
    """
    n = len(points)
    out = [0.0] * n
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            continue
        prev, nxt = points[(i - 1) % n], points[(i + 1) % n]
        out[i] = _angle(_sub(points[i], prev), _sub(nxt, points[i]))
    return out


def find_corners(
    points: Sequence[Vec3], closed: bool, corner_angle: float
) -> list[int]:
    """Finds the true corners of a faceted polyline.

    A vertex is a corner if it turns at least ``corner_angle``, or if it
    breaks the rhythm of the facets around it: it turns at least 5 degrees
    more than, and at least twice as much as, its neighbours.

    Args:
        points: Vertices without duplicates.
        closed: True for a closed ring.
        corner_angle: Corner angle in radians.

    Returns:
        Sorted corner indices; an open polyline always has its two ends.
    """
    n = len(points)
    angles = turning_angles(points, closed)
    corners = []
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            corners.append(i)
            continue
        a = angles[i]
        if not closed and i == 1:
            m = angles[2] if n > 3 else 0.0
        elif not closed and i == n - 2:
            m = angles[n - 3] if n > 3 else 0.0
        else:
            m = max(angles[(i - 1) % n], angles[(i + 1) % n])
        if a >= corner_angle - 1e-9 or (
            a - m >= RHYTHM_EXCESS and a >= RHYTHM_RATIO * m
        ):
            corners.append(i)
    return corners

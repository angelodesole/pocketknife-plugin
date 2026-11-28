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
from typing import NamedTuple

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


PRIMITIVE_FIT = 0.1
LINE_TURN = math.radians(0.01)
LINE_MIN_EDGES = 3
ARC_MIN_VERTICES = 4
ARC_MIN_SWEEP = math.radians(20.0)
REGULARITY = 0.02


class Run(NamedTuple):
    """A run of vertices that becomes one output piece.

    Attributes:
        kind: ``"line"``, ``"arc"``, ``"circle"`` or ``"free"``.
        start: Index of the first vertex.
        end: Index of the last vertex (cyclic on rings: may be < start; for a
            circle it equals ``start``).
        center: Circle centre (arcs and circles).
        normal: Circle plane normal (arcs and circles).
        radius: Circle radius (arcs and circles).
    """

    kind: str
    start: int
    end: int
    center: Vec3 | None = None
    normal: Vec3 | None = None
    radius: float | None = None


def solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Solves a dense linear system by Gaussian elimination with pivoting.

    Args:
        matrix: Square matrix (copied, not modified).
        rhs: Right-hand side.

    Returns:
        The solution, or None if the matrix is singular.
    """
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-14:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        inv = 1.0 / a[col][col]
        for r in range(col + 1, n):
            f = a[r][col] * inv
            if f != 0.0:
                row_r, row_c = a[r], a[col]
                for c in range(col, n + 1):
                    row_r[c] -= f * row_c[c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / a[r][r]
    return x


def best_plane(points: Sequence[Vec3]) -> tuple[Vec3, Vec3, float]:
    """Best-fit plane of a point set.

    Args:
        points: At least three points.

    Returns:
        ``(centroid, unit normal, max distance of the points from the plane)``.
    """
    n = len(points)
    c = (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )
    axes = principal_axes(points)

    def spread(axis: Vec3) -> float:
        return sum(_dot(_sub(p, c), axis) ** 2 for p in points)

    normal = min(axes, key=spread)
    return c, normal, max(abs(_dot(_sub(p, c), normal)) for p in points)


def _frame(normal: Vec3) -> tuple[Vec3, Vec3]:
    helper = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit(_cross(normal, helper))
    return u, _cross(normal, u)


def fit_circle(points: Sequence[Vec3], normal: Vec3) -> tuple[Vec3, float]:
    """Least-squares (Kasa) circle of points in the plane of ``normal``.

    Args:
        points: Points, roughly coplanar.
        normal: Plane normal.

    Returns:
        ``(center, radius)``; the centre lies in the points' mean plane.
    """
    origin = points[0]
    u, v = _frame(normal)
    xy = [(_dot(_sub(p, origin), u), _dot(_sub(p, origin), v)) for p in points]
    ata = [[0.0] * 3 for _ in range(3)]
    atb = [0.0] * 3
    for x, y in xy:
        row = (x, y, 1.0)
        rhs = -(x * x + y * y)
        for i in range(3):
            atb[i] += row[i] * rhs
            for j in range(3):
                ata[i][j] += row[i] * row[j]
    sol = solve(ata, atb)
    if sol is None:
        return origin, math.inf
    d, e, f = sol
    cx, cy = -d / 2.0, -e / 2.0
    r = math.sqrt(max(cx * cx + cy * cy - f, 0.0))
    mean_h = sum(_dot(_sub(p, origin), normal) for p in points) / len(points)
    center = _add(
        origin, _add(_add(_scale(u, cx), _scale(v, cy)), _scale(normal, mean_h))
    )
    return center, r


def _point_segment_distance(p: Vec3, a: Vec3, b: Vec3) -> float:
    ab = _sub(b, a)
    length_sq = _dot(ab, ab)
    if length_sq == 0.0:
        return _dist(p, a)
    t = max(0.0, min(1.0, _dot(_sub(p, a), ab) / length_sq))
    return _dist(p, _add(a, _scale(ab, t)))


def _within(values: Sequence[float], ratio: float) -> bool:
    if len(values) < 2:
        return True
    mean = sum(values) / len(values)
    return all(abs(v - mean) <= ratio * abs(mean) for v in values)


def _is_line(pts: Sequence[Vec3], turns: Sequence[float], tol: float) -> bool:
    if len(pts) < LINE_MIN_EDGES + 1:
        return False
    if any(t > LINE_TURN for t in turns[1:-1]):
        return False
    a, b = pts[0], pts[-1]
    return all(_point_segment_distance(p, a, b) <= PRIMITIVE_FIT * tol for p in pts)


def _same_side(pts: Sequence[Vec3], normal: Vec3) -> bool:
    signs = set()
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        s = _dot(_cross(_sub(b, a), _sub(c, b)), normal)
        if abs(s) > 1e-15:
            signs.add(s > 0)
    return len(signs) <= 1


def _sweep(pts: Sequence[Vec3], center: Vec3) -> float:
    return sum(_angle(_sub(a, center), _sub(b, center)) for a, b in zip(pts, pts[1:]))


def _arc_fit(
    pts: Sequence[Vec3], turns: Sequence[float], tol: float, closed: bool
) -> tuple[Vec3, Vec3, float] | None:
    """Circle of an arc run, or None if the run is not a faceted arc.

    ``turns`` are the turning angles at ``pts`` (the ends' values unused).
    For an open run the centre is taken on the perpendicular bisector of
    the ends, so the arc passes through both end vertices.
    """
    if len(pts) < ARC_MIN_VERTICES:
        return None
    limit = PRIMITIVE_FIT * tol
    edges = [_dist(a, b) for a, b in zip(pts, pts[1:])]
    inner_turns = list(turns) if closed else list(turns[1:-1])
    if not _within(edges, REGULARITY) or not _within(inner_turns, REGULARITY):
        return None
    _, normal, flat = best_plane(pts)
    if flat > limit or not _same_side(pts, normal):
        return None
    center, radius = fit_circle(pts, normal)
    if not closed:
        a, b = pts[0], pts[-1]
        mid = _scale(_add(a, b), 0.5)
        axis = _unit(_cross(normal, _sub(b, a)))
        center = _add(mid, _scale(axis, _dot(_sub(center, mid), axis)))
        radius = _dist(center, a)
    if not math.isfinite(radius):
        return None
    if any(abs(_dist(p, center) - radius) > limit for p in pts):
        return None
    return center, normal, radius


def partition(
    points: Sequence[Vec3], closed: bool, tol: float, corners: Sequence[int]
) -> list[Run]:
    """Splits a polyline into line, arc, circle and free runs.

    Args:
        points: Vertices without duplicates.
        closed: True for a closed ring.
        tol: Tolerance at the vertices.
        corners: Corner indices from ``find_corners``.

    Returns:
        Runs in order, covering every edge exactly once.
    """
    n = len(points)
    turns = turning_angles(points, closed)
    if closed and not corners:
        fit = _arc_fit(points, turns, tol, True)
        if fit is not None and _sweep(list(points) + [points[0]], fit[0]) > math.pi:
            return [Run("circle", 0, 0, *fit)]
        start = max(
            range(n), key=lambda i: (round(abs(turns[i] - turns[i - 1]), 9), -i)
        )
        runs = _partition_stretch(
            points, turns, [(start + k) % n for k in range(n + 1)], tol
        )
        if len(runs) > 2 and runs[0].kind == runs[-1].kind != "free":
            # The seam fell inside a primitive: restart where the last run
            # begins, so the two halves become one run.
            start = runs[-1].start
            runs = _partition_stretch(
                points, turns, [(start + k) % n for k in range(n + 1)], tol
            )
        return runs
    elif closed:
        cs = sorted(corners)
        stretches = []
        for a, b in zip(cs, cs[1:] + [cs[0] + n]):
            stretches.append([k % n for k in range(a, b + 1)])
    else:
        cs = sorted(corners)
        stretches = [list(range(a, b + 1)) for a, b in zip(cs, cs[1:])]
    runs: list[Run] = []
    for idx in stretches:
        runs += _partition_stretch(points, turns, idx, tol)
    return runs


def _partition_stretch(
    points: Sequence[Vec3], turns: Sequence[float], idx: list[int], tol: float
) -> list[Run]:
    out: list[Run] = []
    free_start = None
    p = 0
    last = len(idx) - 1

    def flush(end: int) -> None:
        nonlocal free_start
        if free_start is not None and end > free_start:
            pts = [points[i] for i in idx[free_start : end + 1]]
            straight = all(
                _point_segment_distance(q, pts[0], pts[-1]) <= PRIMITIVE_FIT * tol
                for q in pts
            )
            kind = "line" if end - free_start == 1 or straight else "free"
            out.append(Run(kind, idx[free_start], idx[end]))
        free_start = None

    while p < last:
        best_line = None
        q = p + LINE_MIN_EDGES
        while q <= last:
            sub = [points[i] for i in idx[p : q + 1]]
            if not _is_line(sub, [turns[i] for i in idx[p : q + 1]], tol):
                break
            best_line = q
            q += 1
        best_arc, arc_fit = None, None
        q = p + ARC_MIN_VERTICES - 1
        while q <= last:
            sub = [points[i] for i in idx[p : q + 1]]
            fit = _arc_fit(sub, [turns[i] for i in idx[p : q + 1]], tol, False)
            if fit is None:
                break
            if _sweep(sub, fit[0]) >= ARC_MIN_SWEEP:
                best_arc, arc_fit = q, fit
            q += 1
        if best_line is None and best_arc is None:
            if free_start is None:
                free_start = p
            p += 1
            continue
        flush(p)
        if best_arc is not None and (best_line is None or best_arc > best_line):
            out.append(Run("arc", idx[p], idx[best_arc], *arc_fit))
            p = best_arc
        else:
            out.append(Run("line", idx[p], idx[best_line]))
            p = best_line
    flush(last)
    return out

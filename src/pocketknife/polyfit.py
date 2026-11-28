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


# B-spline fitting ------------------------------------------------------------


def centripetal_params(points: Sequence[Vec3]) -> list[float]:
    """Centripetal parameters of points, from 0 to 1.

    Args:
        points: At least two distinct points.

    Returns:
        One parameter per point.
    """
    steps = [math.sqrt(_dist(a, b)) for a, b in zip(points, points[1:])]
    total = sum(steps) or 1.0
    out, acc = [0.0], 0.0
    for s in steps:
        acc += s
        out.append(acc / total)
    out[-1] = 1.0
    return out


def averaged_knots(params: Sequence[float], count: int, degree: int) -> list[float]:
    """Clamped knot vector for a least-squares fit (Piegl-Tiller 9.68-9.69).

    Args:
        params: Parameters of the fitted points.
        count: Number of control points.
        degree: Curve degree.

    Returns:
        The full knot vector, ``count + degree + 1`` values.
    """
    m = len(params)
    inner = []
    d = m / (count - degree)
    for j in range(1, count - degree):
        i = int(j * d)
        a = j * d - i
        inner.append((1.0 - a) * params[i - 1] + a * params[i])
    return [0.0] * (degree + 1) + inner + [1.0] * (degree + 1)


def _span(degree: int, knots: Sequence[float], count: int, u: float) -> int:
    if u >= knots[count]:
        return count - 1
    lo, hi = degree, count
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if u < knots[mid]:
            hi = mid
        else:
            lo = mid
    return lo


def _basis(degree: int, knots: Sequence[float], span: int, u: float) -> list[float]:
    """Non-zero basis functions at ``u`` (Piegl-Tiller A2.2)."""
    n = [1.0] + [0.0] * degree
    left = [0.0] * (degree + 1)
    right = [0.0] * (degree + 1)
    for j in range(1, degree + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            denom = right[r + 1] + left[j - r]
            temp = n[r] / denom if denom != 0.0 else 0.0
            n[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        n[j] = saved
    return n


def bspline_point(
    degree: int, ctrl: Sequence[Vec3], knots: Sequence[float], u: float
) -> Vec3:
    """Point of a non-rational B-spline.

    Args:
        degree: Degree.
        ctrl: Control points.
        knots: Full clamped knot vector.
        u: Parameter in [0, 1].

    Returns:
        The point.
    """
    span = _span(degree, knots, len(ctrl), u)
    basis = _basis(degree, knots, span, u)
    x = y = z = 0.0
    for k, b in enumerate(basis):
        p = ctrl[span - degree + k]
        x += b * p[0]
        y += b * p[1]
        z += b * p[2]
    return (x, y, z)


def _derivative(degree: int, ctrl: Sequence[Vec3], knots: Sequence[float]):
    """Derivative curve ``(degree - 1, ctrl, knots)`` of a B-spline."""
    if degree == 0:
        return 0, [(0.0, 0.0, 0.0)], [0.0, 1.0]
    dctrl = []
    for i in range(len(ctrl) - 1):
        span = knots[i + degree + 1] - knots[i + 1]
        f = degree / span if span > 0.0 else 0.0
        dctrl.append(_scale(_sub(ctrl[i + 1], ctrl[i]), f))
    return degree - 1, dctrl, list(knots[1:-1])


def _project(
    points: Sequence[Vec3], curve, params: Sequence[float], steps: int = 4
) -> tuple[list[float], float]:
    """Newton projection of points on a curve, starting from ``params``.

    Returns:
        ``(parameters of the closest points, largest distance)``.
    """
    degree, ctrl, knots = curve
    d1 = _derivative(degree, ctrl, knots)
    d2 = _derivative(*d1) if d1[0] > 0 else (0, [(0.0, 0.0, 0.0)], [0.0, 1.0])
    out, worst = [], 0.0
    for q, u in zip(points, params):
        best_u = u
        c = bspline_point(degree, ctrl, knots, u)
        best = _dist(c, q)
        t = u
        for _ in range(steps):
            c = bspline_point(degree, ctrl, knots, t)
            c1 = bspline_point(*d1, t)
            c2 = bspline_point(*d2, t) if d2[1] else (0.0, 0.0, 0.0)
            diff = _sub(c, q)
            f = _dot(diff, c1)
            df = _dot(c1, c1) + _dot(diff, c2)
            if df <= 0.0:
                break
            t = min(1.0, max(0.0, t - f / df))
            d = _dist(bspline_point(degree, ctrl, knots, t), q)
            if d < best:
                best, best_u = d, t
        out.append(best_u)
        worst = max(worst, best)
    return out, worst


def max_deviation(
    points: Sequence[Vec3], degree: int, ctrl: Sequence[Vec3], knots: Sequence[float]
) -> float:
    """Largest distance from the points to the curve.

    Args:
        points: Points that were fitted.
        degree: Degree.
        ctrl: Control points.
        knots: Full clamped knot vector.

    Returns:
        The maximum distance.
    """
    curve = (degree, ctrl, knots)
    params = centripetal_params(points)
    # Start each projection from the best of a coarse sampling.
    samples = [k / 64 for k in range(65)]
    pts = [bspline_point(degree, ctrl, knots, u) for u in samples]
    starts = []
    for q, u in zip(points, params):
        k = min(range(65), key=lambda i: _dist(pts[i], q))
        starts.append(
            samples[k]
            if _dist(pts[k], q) < _dist(bspline_point(degree, ctrl, knots, u), q)
            else u
        )
    return _project(points, curve, starts)[1]


MAX_CORRECTIONS = 40


def fit_with(
    points: Sequence[Vec3],
    count: int,
    t_start: Vec3 | None,
    t_end: Vec3 | None,
    tol: float | None = None,
):
    """Least-squares B-spline with fixed ends and optional end tangents.

    Parameters are corrected by projecting the points on each fit (Hoschek)
    until the fit stops improving or, with ``tol``, is clearly in or out.

    Args:
        points: Points to fit (at least two).
        count: Number of control points.
        t_start: Unit tangent direction at the start, or None.
        t_end: Unit tangent direction at the end, or None.
        tol: Optional tolerance, used only to stop the correction early.

    Returns:
        ``(degree, ctrl, knots)``, or None if the system is singular.
    """
    return _fit_core(points, count, t_start, t_end, tol)[0]


def _fit_core(points, count, t_start, t_end, tol):
    """``fit_with`` that also returns the deviation of its best fit."""
    count = max(2, count)
    degree = min(3, count - 1)
    params = centripetal_params(points)
    knots = averaged_knots(params, count, degree)
    best, best_dev, previous = None, math.inf, math.inf
    for it in range(MAX_CORRECTIONS + 1):
        fit = _solve_fit(points, params, knots, count, degree, t_start, t_end)
        if fit is None:
            return best, best_dev
        params, dev = _project(points, fit, params, steps=1)
        if dev < best_dev:
            best, best_dev = fit, dev
        if tol is not None and dev <= 0.5 * tol:
            break
        rate = dev / previous if previous > 0.0 else 0.0
        if rate > 0.97:
            break
        if tol is not None and it >= 2:
            # Linear convergence: stop if even the remaining iterations at
            # this rate cannot bring the deviation within tolerance.
            if dev * rate ** (MAX_CORRECTIONS - it) > tol:
                break
        previous = dev
    return best, best_dev


def _solve_fit(points, params, knots, count, degree, t_start, t_end):
    """One least-squares solve at fixed parameters and knots."""
    p0, pn = points[0], points[-1]
    use_tangents = count >= 4
    # Each control point is (constant, [(var, coeff_vector)]).
    var = 0
    layout = []
    for i in range(count):
        if i == 0:
            layout.append(("fixed", p0))
        elif i == count - 1:
            layout.append(("fixed", pn))
        elif i == 1 and use_tangents and t_start is not None:
            layout.append(("ray", p0, t_start, var))
            var += 1
        elif i == count - 2 and use_tangents and t_end is not None:
            layout.append(("ray", pn, _scale(t_end, -1.0), var))
            var += 1
        else:
            layout.append(("free", var))
            var += 3
    if var == 0:
        return degree, [p0, pn], knots
    ata = [[0.0] * var for _ in range(var)]
    atb = [0.0] * var
    for q, u in zip(points, params):
        span = _span(degree, knots, count, u)
        basis = _basis(degree, knots, span, u)
        for c in range(3):
            terms: dict[int, float] = {}
            const = 0.0
            for k, b in enumerate(basis):
                if b == 0.0:
                    continue
                entry = layout[span - degree + k]
                if entry[0] == "fixed":
                    const += b * entry[1][c]
                elif entry[0] == "ray":
                    const += b * entry[1][c]
                    terms[entry[3]] = terms.get(entry[3], 0.0) + b * entry[2][c]
                else:
                    terms[entry[1] + c] = terms.get(entry[1] + c, 0.0) + b
            rhs = q[c] - const
            items = list(terms.items())
            for i, ci in items:
                atb[i] += ci * rhs
                row = ata[i]
                for j, cj in items:
                    row[j] += ci * cj
    sol = solve(ata, atb)
    if sol is None:
        return None
    ctrl = []
    for entry in layout:
        if entry[0] == "fixed":
            ctrl.append(entry[1])
        elif entry[0] == "ray":
            ctrl.append(_add(entry[1], _scale(entry[2], sol[entry[3]])))
        else:
            v = entry[1]
            ctrl.append((sol[v], sol[v + 1], sol[v + 2]))
    return degree, ctrl, knots


def _search(points, tol, t_start, t_end):
    """Smallest control-point count whose fit is within tol, or None."""
    m = len(points)
    cache = {}

    def ok(n: int):
        # The projection distance of the fit is an upper bound of the true
        # deviation, so a pass here is a real pass.
        if n not in cache:
            fit, dev = _fit_core(points, n, t_start, t_end, tol)
            cache[n] = fit if fit is not None and dev <= tol else None
        return cache[n]

    low, high = 3, None
    n = 4
    while n < m:
        if ok(n):
            high = n
            break
        low = n
        n *= 2
    if high is None:
        if not ok(m):
            return None
        high = m
    while high - low > 1:
        mid = (low + high) // 2
        if ok(mid):
            high = mid
        else:
            low = mid
    while high > 4 and ok(high - 1):
        high -= 1
    return ok(high)


def fit_free(
    points: Sequence[Vec3], tol: float, t_start: Vec3 | None, t_end: Vec3 | None
) -> tuple[str, tuple]:
    """Fits a free run with the fewest control points within tolerance.

    Args:
        points: The run's vertices (at least two).
        tol: Tolerance at the vertices.
        t_start: Unit tangent direction imposed at the start, or None.
        t_end: Unit tangent direction imposed at the end, or None.

    Returns:
        ``("nurbs", (degree, ctrl, knots))`` or, if nothing fits,
        ``("polyline", (points,))``.
    """
    pts = list(points)
    m = len(pts)
    if m == 2:
        return "nurbs", (1, pts, [0.0, 0.0, 1.0, 1.0])
    if m == 3:
        fit = fit_with(pts, 3, None, None)
        if fit is not None and max_deviation(pts, *fit) <= tol:
            return "nurbs", fit
        return "polyline", (pts,)
    for ts, te in ((t_start, t_end), (None, None)):
        fit = _search(pts, tol, ts, te)
        if fit is not None:
            return "nurbs", fit
        if ts is None and te is None:
            break
    return "polyline", (pts,)


# Assembly ------------------------------------------------------------------


def _run_points(points: Sequence[Vec3], run: Run) -> list[Vec3]:
    n = len(points)
    if run.kind == "circle":
        return list(points) + [points[0]]
    count = (run.end - run.start) % n or n
    return [points[(run.start + k) % n] for k in range(count + 1)]


def _circumcenter(a: Vec3, b: Vec3, c: Vec3) -> Vec3 | None:
    ab, ac = _sub(b, a), _sub(c, a)
    n = _cross(ab, ac)
    nn = _dot(n, n)
    if nn < 1e-30:
        return None
    term = _add(
        _scale(_cross(n, ab), _dot(ac, ac)), _scale(_cross(ac, n), _dot(ab, ab))
    )
    return _add(a, _scale(term, 1.0 / (2.0 * nn)))


def _arc_tangent(center: Vec3, normal: Vec3, at: Vec3, toward: Vec3) -> Vec3:
    """Unit tangent of a circle at ``at``, oriented toward ``toward``."""
    t = _unit(_cross(normal, _sub(at, center)))
    return t if _dot(t, _sub(toward, at)) >= 0 else _scale(t, -1.0)


def _constrained_center(
    pts: Sequence[Vec3], normal: Vec3, start_dir: Vec3 | None, end_dir: Vec3 | None
) -> Vec3 | None:
    """Centre of an arc tangent to the given line directions at its ends."""
    a, b = pts[0], pts[-1]
    lines = []
    if start_dir is not None:
        lines.append((a, _unit(_cross(normal, start_dir))))
    if end_dir is not None:
        lines.append((b, _unit(_cross(normal, end_dir))))
    if not lines:
        return None
    if len(lines) == 2:
        (p, u), (q, v) = lines
        # p + s u = q + t v, least squares in the plane.
        uv = _dot(u, v)
        denom = 1.0 - uv * uv
        if denom < 1e-12:
            return None
        w = _sub(q, p)
        s = (_dot(w, u) - uv * _dot(w, v)) / denom
        return _add(p, _scale(u, s))
    p, u = lines[0]
    values = []
    for q in pts:
        d = _sub(q, p)
        den = 2.0 * _dot(d, u)
        if abs(den) > 1e-12:
            values.append(_dot(d, d) / den)
    if not values:
        return None
    return _add(p, _scale(u, sum(values) / len(values)))


def _line_dir(points: Sequence[Vec3], run: Run) -> Vec3:
    pts = _run_points(points, run)
    return _unit(_sub(pts[-1], pts[0]))


def _end_tangent(points: Sequence[Vec3], run: Run, at_start: bool) -> Vec3:
    """Forward unit tangent of a primitive run at its start or end."""
    pts = _run_points(points, run)
    if run.kind == "line":
        return _line_dir(points, run)
    if at_start:
        return _arc_tangent(run.center, run.normal, pts[0], pts[1])
    t = _arc_tangent(run.center, run.normal, pts[-1], pts[-2])
    return _scale(t, -1.0)


def _arc_piece(
    points: Sequence[Vec3],
    run: Run,
    tol: float,
    start_dir: Vec3 | None,
    end_dir: Vec3 | None,
):
    pts = _run_points(points, run)
    center, radius = run.center, run.radius
    if start_dir is not None or end_dir is not None:
        c = _constrained_center(pts, run.normal, start_dir, end_dir)
        if c is not None:
            r = _dist(c, pts[0])
            if all(abs(_dist(p, c) - r) <= tol for p in pts):
                center, radius = c, r
    mid_vertex = pts[len(pts) // 2]
    pmid = _add(center, _scale(_unit(_sub(mid_vertex, center)), radius))
    return ("arc", (pts[0], pmid, pts[-1])), center


def rebuild(
    points: Sequence[Vec3], closed: bool, tol: float, corner_angle: float
) -> list[tuple[str, tuple]]:
    """Rebuilds a faceted polyline into lines, arcs, circles and NURBS.

    Args:
        points: Input vertices.
        closed: True for a closed ring.
        tol: Tolerance at the input vertices.
        corner_angle: Corner angle in radians.

    Returns:
        Pieces in order: ``("line", (p0, p1))``, ``("arc", (p0, pmid, p1))``,
        ``("circle", (center, normal, radius, start))``,
        ``("nurbs", (degree, ctrl, knots))`` or ``("polyline", (points,))``.
        Consecutive pieces share their end vertices exactly.
    """
    pts = dedupe(points, closed, tol / 100.0)
    if len(pts) < 2 or (closed and len(pts) < 3):
        return []
    corners = find_corners(pts, closed, corner_angle)
    runs = partition(pts, closed, tol, corners)
    corner_set = set(corners)
    n = len(pts)

    if closed and len(runs) == 1 and runs[0].kind == "free":
        turns = turning_angles(pts, True)
        s = max(range(n), key=lambda i: turns[i])
        ring = [pts[(s + k) % n] for k in range(n + 1)]
        t = _unit(_sub(pts[(s + 1) % n], pts[(s - 1) % n]))
        return [fit_free(ring, tol, t, t)]

    def neighbour(k: int, offset: int) -> Run | None:
        j = k + offset
        if closed:
            return runs[j % len(runs)] if len(runs) > 1 else None
        return runs[j] if 0 <= j < len(runs) else None

    pieces = []
    for k, run in enumerate(runs):
        if run.kind == "circle":
            center, normal, radius = run.center, run.normal, run.radius
            radial = _sub(pts[0], center)
            radial = _sub(radial, _scale(normal, _dot(radial, normal)))
            start = _add(center, _scale(_unit(radial), radius))
            pieces.append(("circle", (center, normal, radius, start)))
            continue
        rp = _run_points(pts, run)
        if run.kind == "line":
            pieces.append(("line", (rp[0], rp[-1])))
            continue
        prev, nxt = neighbour(k, -1), neighbour(k, 1)
        smooth_start = run.start not in corner_set
        smooth_end = run.end not in corner_set
        if run.kind == "arc":
            start_dir = (
                _line_dir(pts, prev)
                if prev is not None and prev.kind == "line" and smooth_start
                else None
            )
            end_dir = (
                _line_dir(pts, nxt)
                if nxt is not None and nxt.kind == "line" and smooth_end
                else None
            )
            piece, _ = _arc_piece(pts, run, tol, start_dir, end_dir)
            pieces.append(piece)
            continue
        t_start = (
            _end_tangent(pts, prev, at_start=False)
            if prev is not None and prev.kind in ("line", "arc") and smooth_start
            else None
        )
        t_end = (
            _end_tangent(pts, nxt, at_start=True)
            if nxt is not None and nxt.kind in ("line", "arc") and smooth_end
            else None
        )
        pieces.append(fit_free(rp, tol, t_start, t_end))
    return pieces

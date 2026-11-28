"""Rhino adapter for rebuilding faceted curves (see ``pocketknife.polyfit``).

Only importable inside Rhino 8 (CPython 3.9 runtime).
"""

from __future__ import annotations

import math

import Rhino.Geometry as rg

from pocketknife.polyfit import rebuild


def _tuple(p) -> tuple:
    return (p.X, p.Y, p.Z)


def _pt(p) -> rg.Point3d:
    return rg.Point3d(p[0], p[1], p[2])


def _span_vertices(span: rg.Curve, tol: float) -> list:
    """Vertices of a smooth span, evenly spaced by length.

    Even spacing keeps arc spans uniformly faceted, so they are recognised as
    arcs; the count comes from an adaptive polyline at ``tol / 10``.
    """
    approx = span.ToPolyline(0, 0, 0.0, 0.0, 0.0, tol / 10.0, 0.0, 0.0, True)
    count = 8
    if approx is not None:
        count = max(count, approx.PointCount - 1)
    params = span.DivideByCount(count, True)
    if not params:
        return [_tuple(span.PointAtStart), _tuple(span.PointAtEnd)]
    return [_tuple(span.PointAt(t)) for t in params] + [_tuple(span.PointAtEnd)]


def curve_vertices(curve: rg.Curve, tol: float) -> tuple[list, bool]:
    """Vertices of a curve for rebuilding.

    Polylines (and degree-1 or line-only curves) give their vertices. Other
    curves are split at their kinks, which become corners, and each smooth
    span is sampled evenly.

    Args:
        curve: Input curve.
        tol: Rebuild tolerance.

    Returns:
        ``(vertices, closed)``.
    """
    closed = curve.IsClosed
    ok, polyline = curve.TryGetPolyline()
    if ok:
        return [_tuple(p) for p in polyline], closed
    domain = curve.Domain
    cuts = [domain.Min]
    t = domain.Min
    while True:
        found, t = curve.GetNextDiscontinuity(
            rg.Continuity.C1_continuous, t, domain.Max
        )
        if not found:
            break
        cuts.append(t)
    cuts.append(domain.Max)
    vertices = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a <= 0.0:
            continue
        span = curve.Trim(a, b)
        if span is None:
            continue
        pts = _span_vertices(span, tol)
        vertices += pts if not vertices else pts[1:]
    return vertices, closed


def _nurbs(degree: int, ctrl: list, knots: list) -> rg.NurbsCurve:
    curve = rg.NurbsCurve(3, False, degree + 1, len(ctrl))
    for i, p in enumerate(ctrl):
        curve.Points.SetPoint(i, _pt(p))
    for i, k in enumerate(knots[1:-1]):
        curve.Knots[i] = k
    return curve


def piece_curve(piece) -> rg.Curve | None:
    """Rhino curve of one piece from ``polyfit.rebuild``.

    Args:
        piece: ``(kind, data)``.

    Returns:
        The curve, or None if Rhino could not build it.
    """
    kind, data = piece
    if kind == "line":
        return rg.LineCurve(_pt(data[0]), _pt(data[1]))
    if kind == "arc":
        arc = rg.Arc(_pt(data[0]), _pt(data[1]), _pt(data[2]))
        return rg.ArcCurve(arc) if arc.IsValid else None
    if kind == "circle":
        center, normal, radius, start = data
        c = _pt(center)
        x = _pt(start) - c
        y = rg.Vector3d.CrossProduct(rg.Vector3d(normal[0], normal[1], normal[2]), x)
        return rg.ArcCurve(rg.Circle(rg.Plane(c, x, y), radius))
    if kind == "nurbs":
        return _nurbs(*data)
    polyline = rg.Polyline()
    for p in data[0]:
        polyline.Add(_pt(p))
    return rg.PolylineCurve(polyline)


def pieces_to_curve(pieces: list) -> rg.Curve | None:
    """Joins pieces into one curve (a PolyCurve when there are several).

    Args:
        pieces: Pieces from ``polyfit.rebuild``.

    Returns:
        The curve, or None if any piece or the join fails.
    """
    curves = [piece_curve(p) for p in pieces]
    if not curves or any(c is None or not c.IsValid for c in curves):
        return None
    if len(curves) == 1:
        return curves[0]
    joined = rg.PolyCurve()
    for c in curves:
        if not joined.Append(c):
            return None
    return joined if joined.IsValid else None


def control_point_count(curve: rg.Curve) -> int:
    """Number of control points of a curve as a NURBS (for the summary).

    Args:
        curve: Any curve.

    Returns:
        The count, or 0 if Rhino cannot convert it.
    """
    nurbs = curve.ToNurbsCurve()
    return nurbs.Points.Count if nurbs is not None else 0


def rebuild_curve(curve: rg.Curve, tol: float, corner_angle_deg: float):
    """Rebuilds one curve.

    Args:
        curve: Input curve.
        tol: Tolerance at the input vertices.
        corner_angle_deg: Corner angle in degrees.

    Returns:
        ``(curve or None, kinds)`` where ``kinds`` lists the piece kinds.
    """
    if curve.IsLinear(tol) and not curve.IsClosed:
        return rg.LineCurve(curve.PointAtStart, curve.PointAtEnd), ["line"]
    ok, circle = curve.TryGetCircle(tol)
    if ok and curve.IsClosed:
        return rg.ArcCurve(circle), ["circle"]
    ok, arc = curve.TryGetArc(tol)
    if ok and not curve.IsClosed:
        return rg.ArcCurve(arc), ["arc"]
    vertices, closed = curve_vertices(curve, tol)
    pieces = rebuild(vertices, closed, tol, math.radians(corner_angle_deg))
    if not pieces:
        return None, []
    return pieces_to_curve(pieces), [kind for kind, _ in pieces]

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


ARC_FACET = math.radians(5.0)
KINK = math.radians(0.1)


def _span_vertices(span: rg.Curve, tol: float) -> list:
    """Vertices of a smooth span.

    Straight spans give their ends. Arc spans are divided evenly (facets of
    at most 5 degrees), so they are recognised as arcs. Free spans use an
    adaptive polyline at ``tol / 10``, dense where the curve bends.
    """
    if span.IsLinear(tol):
        return [_tuple(span.PointAtStart), _tuple(span.PointAtEnd)]
    ok, arc = span.TryGetArc(tol)
    if ok:
        count = max(4, int(math.ceil(arc.Angle / ARC_FACET)))
        params = span.DivideByCount(count, True)
        if params:
            return [_tuple(span.PointAt(t)) for t in params] + [_tuple(span.PointAtEnd)]
    approx = span.ToPolyline(0, 0, 0.0, 0.0, 0.0, tol / 10.0, 0.0, 0.0, True)
    if approx is None:
        return [_tuple(span.PointAtStart), _tuple(span.PointAtEnd)]
    return [_tuple(approx.Point(i)) for i in range(approx.PointCount)]


def curve_vertices(curve: rg.Curve, tol: float) -> tuple[list, bool, list]:
    """Vertices of a curve for rebuilding.

    Polylines give their vertices. Other curves are split at their C1
    discontinuities; each smooth span is sampled by ``_span_vertices``, and
    every split where the tangent really turns (a kink) is a forced corner.

    Args:
        curve: Input curve.
        tol: Rebuild tolerance.

    Returns:
        ``(vertices, closed, forced corner indices)``.
    """
    closed = curve.IsClosed
    ok, polyline = curve.TryGetPolyline()
    if ok:
        return [_tuple(p) for p in polyline], closed, []
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
    vertices, forced, previous = [], [], None
    for a, b in zip(cuts, cuts[1:]):
        if b - a <= 0.0:
            continue
        span = curve.Trim(a, b)
        if span is None:
            continue
        if previous is not None:
            turn = rg.Vector3d.VectorAngle(previous.TangentAtEnd, span.TangentAtStart)
            if turn > KINK:
                forced.append(len(vertices) - 1)
        pts = _span_vertices(span, tol)
        vertices += pts if not vertices else pts[1:]
        previous = span
    if closed and previous is not None and vertices:
        first = curve.Trim(cuts[0], cuts[1])
        if first is not None:
            turn = rg.Vector3d.VectorAngle(previous.TangentAtEnd, first.TangentAtStart)
            if turn > KINK:
                forced.append(0)
    return vertices, closed, forced


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
    vertices, closed, forced = curve_vertices(curve, tol)
    pieces = rebuild(vertices, closed, tol, math.radians(corner_angle_deg), forced)
    if not pieces:
        return None, []
    return pieces_to_curve(pieces), [kind for kind, _ in pieces]

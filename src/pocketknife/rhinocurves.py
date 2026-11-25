"""Rhino adapter for curve network cleaning (see ``pocketknife.curvegraph``).

Only importable inside Rhino 8 (CPython 3.9 runtime).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Sequence
from typing import NamedTuple

import Rhino.Geometry as rg
from Rhino.Geometry.Intersect import Intersection

from pocketknife.curvegraph import (
    ARC,
    FREE,
    LINE,
    Segment,
    arc_segment,
    build_chains,
    compact_chain,
    drop_slivers,
    line_segment,
    remove_overlaps,
)


class CleanResult(NamedTuple):
    """Result of ``clean_curves``.

    Attributes:
        curves: New curves.
        sources: Per new curve, the index of the input curve whose layer and
            attributes it takes (the input of its longest piece).
        unchanged: Inputs that came out identical; leave them in place.
        skipped: Non-planar inputs, left untouched.
        removed: Number of overlapping stretches removed.
    """

    curves: list
    sources: list
    unchanged: list
    skipped: list
    removed: int


class _Piece(NamedTuple):
    curve: rg.Curve
    source: int


# Planes -------------------------------------------------------------------


def _canonical_normal(normal: rg.Vector3d) -> rg.Vector3d:
    n = rg.Vector3d(normal)
    n.Unitize()
    largest = max((n.X, n.Y, n.Z), key=abs)
    return n * -1.0 if largest < 0 else n


def _group_plane(point: rg.Point3d, normal: rg.Vector3d) -> rg.Plane:
    """Plane through ``point``; world-aligned when the normal is world Z."""
    n = _canonical_normal(normal)
    if n.IsParallelTo(rg.Vector3d.ZAxis, 1e-9) != 0:
        return rg.Plane(rg.Point3d(0, 0, point.Z), rg.Vector3d.ZAxis)
    return rg.Plane(point, n)


def _line_plane(curve: rg.Curve) -> rg.Plane:
    """Plane containing a straight curve, with normal closest to world Z."""
    d = curve.PointAtEnd - curve.PointAtStart
    d.Unitize()
    z = rg.Vector3d.ZAxis
    n = z - d * (z * d)
    if not n.Unitize():
        n = rg.Vector3d.XAxis - d * (rg.Vector3d.XAxis * d)
        n.Unitize()
    return _group_plane(curve.PointAtStart, n)


def _same_plane(a: rg.Plane, b: rg.Plane, tol: float, angle_tol: float) -> bool:
    if a.ZAxis.IsParallelTo(b.ZAxis, angle_tol) == 0:
        return False
    return abs(a.DistanceTo(b.Origin)) <= tol


def _contains(plane: rg.Plane, curve: rg.Curve, tol: float) -> bool:
    return all(
        abs(plane.DistanceTo(p)) <= tol for p in (curve.PointAtStart, curve.PointAtEnd)
    )


# Conversion -----------------------------------------------------------------


def _uv(plane: rg.Plane, point: rg.Point3d) -> tuple:
    ok, u, v = plane.ClosestParameter(point)
    return (u, v)


def _dir(plane: rg.Plane, vector: rg.Vector3d) -> tuple:
    x, y = vector * plane.XAxis, vector * plane.YAxis
    n = math.hypot(x, y)
    return (x / n, y / n) if n else (0.0, 0.0)


def _explode(curve: rg.Curve) -> list:
    pieces = curve.DuplicateSegments()
    return list(pieces) if pieces else [curve.DuplicateCurve()]


def _to_segments(
    piece: rg.Curve,
    source: int,
    plane: rg.Plane,
    tol: float,
    free_curves: list,
) -> list:
    """Converts one curve piece into line, arc or free segments."""
    ok, polyline = piece.TryGetPolyline()
    if ok and polyline.Count >= 2:
        return [
            line_segment(_uv(plane, a), _uv(plane, b), source)
            for a, b in zip(list(polyline)[:-1], list(polyline)[1:])
        ]
    if piece.IsLinear(tol):
        return [
            line_segment(
                _uv(plane, piece.PointAtStart), _uv(plane, piece.PointAtEnd), source
            )
        ]
    ok, arc = piece.TryGetArc(plane, tol)
    if ok:
        center = _uv(plane, arc.Center)
        start = _uv(plane, piece.PointAtStart)
        start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
        sign = 1.0 if arc.Plane.ZAxis * plane.ZAxis > 0 else -1.0
        segment = arc_segment(
            center, arc.Radius, start_angle, sign * arc.AngleRadians, source
        )
        end = _uv(plane, piece.PointAtEnd)
        if math.hypot(segment.end[0] - end[0], segment.end[1] - end[1]) <= tol:
            return [segment]
    free_curves.append(piece)
    return [
        Segment(
            FREE,
            _uv(plane, piece.PointAtStart),
            _uv(plane, piece.PointAtEnd),
            _dir(plane, piece.TangentAtStart),
            _dir(plane, piece.TangentAtEnd * -1.0),
            piece.GetLength(),
            source=source,
            ref=len(free_curves) - 1,
        )
    ]


def _is_free(piece: rg.Curve, tol: float) -> bool:
    if piece.IsLinear(tol):
        return False
    ok, _ = piece.TryGetPolyline()
    if ok:
        return False
    ok, _ = piece.TryGetArc(tol)
    return not ok


# Overlaps involving free curves ----------------------------------------------


def _remainder(curve: rg.Curve, overlaps: list, tol: float) -> list:
    """Parts of ``curve`` outside the overlap intervals."""
    domain = curve.Domain
    cuts = sorted((iv.Min, iv.Max) for iv in overlaps)
    parts, t = [], domain.Min
    for lo, hi in cuts:
        if lo > t:
            parts.append(rg.Interval(t, lo))
        t = max(t, hi)
    if t < domain.Max:
        parts.append(rg.Interval(t, domain.Max))
    out = []
    for interval in parts:
        piece = curve.Trim(interval)
        if piece is not None and piece.GetLength() > tol:
            out.append(piece)
    return out


def _remove_free_overlaps(pieces: list, tol: float) -> tuple:
    """Trims the shorter curve of every overlapping pair involving a free one.

    Returns:
        ``(pieces, removed, touched)``: the remaining pieces, the number of
        overlaps removed and the sources of the trimmed curves.
    """
    removed = 0
    touched = set()
    for _ in range(3):
        alive = list(pieces)
        free = [_is_free(p.curve, tol) for p in alive]
        boxes = [p.curve.GetBoundingBox(False) for p in alive]
        order = sorted(range(len(alive)), key=lambda i: boxes[i].Min.X)
        dead, extra, changed = set(), [], False
        for k, i in enumerate(order):
            for j in order[k + 1 :]:
                if boxes[j].Min.X > boxes[i].Max.X + tol:
                    break
                if i in dead or j in dead or not (free[i] or free[j]):
                    continue
                bi, bj = boxes[i], boxes[j]
                if (
                    bj.Min.Y > bi.Max.Y + tol
                    or bi.Min.Y > bj.Max.Y + tol
                    or bj.Min.Z > bi.Max.Z + tol
                    or bi.Min.Z > bj.Max.Z + tol
                ):
                    continue
                a, b = alive[i].curve, alive[j].curve
                events = Intersection.CurveCurve(a, b, tol, tol)
                if events is None:
                    continue
                overlaps = [e for e in events if e.IsOverlap]
                if not overlaps:
                    continue
                trim_a = a.GetLength() <= b.GetLength()
                victim = i if trim_a else j
                intervals = [e.OverlapA if trim_a else e.OverlapB for e in overlaps]
                rest = _remainder(alive[victim].curve, intervals, tol)
                dead.add(victim)
                touched.add(alive[victim].source)
                extra += [_Piece(c, alive[victim].source) for c in rest]
                removed += len(overlaps)
                changed = True
        pieces = [p for k, p in enumerate(alive) if k not in dead] + extra
        if not changed:
            break
    return pieces, removed, touched


# Assembly -------------------------------------------------------------------


def _pt(plane: rg.Plane, p: tuple) -> rg.Point3d:
    return plane.PointAt(p[0], p[1])


def _arc_curve(plane: rg.Plane, s: Segment, start, end) -> rg.Curve:
    """Arc of segment ``s`` running from 3D ``start`` to 3D ``end``."""
    center = _pt(plane, s.center)
    if abs(abs(s.sweep) - 2 * math.pi) < 1e-9:
        x = start - center
        normal = plane.ZAxis if s.sweep > 0 else plane.ZAxis * -1.0
        y = rg.Vector3d.CrossProduct(normal, x)
        circle = rg.Circle(rg.Plane(center, x, y), s.radius)
        return rg.ArcCurve(circle)
    mid_angle = s.start_angle + 0.5 * s.sweep
    mid = (
        s.center[0] + s.radius * math.cos(mid_angle),
        s.center[1] + s.radius * math.sin(mid_angle),
    )
    return rg.ArcCurve(rg.Arc(start, _pt(plane, mid), end))


def _free_curve(free_curves: list, s: Segment, start, end):
    curve = free_curves[s.ref].DuplicateCurve()
    if curve.PointAtEnd.DistanceTo(start) < curve.PointAtStart.DistanceTo(start):
        curve.Reverse()
    curve.SetStartPoint(start)
    curve.SetEndPoint(end)
    return curve


def _assemble(
    plane: rg.Plane,
    parts: list,
    closed: bool,
    free_curves: list,
) -> rg.Curve:
    """Builds one curve from oriented segments, snapping shared endpoints."""
    points = [_pt(plane, parts[0].start)]
    for s in parts:
        points.append(_pt(plane, s.end))
    if closed:
        points[-1] = points[0]
    if all(s.kind == LINE for s in parts):
        polyline = rg.Polyline()
        for point in points:
            polyline.Add(point)
        return rg.PolylineCurve(polyline)
    curve = rg.PolyCurve()
    for k, s in enumerate(parts):
        start, end = points[k], points[k + 1]
        if s.kind == LINE:
            piece = rg.LineCurve(start, end)
        elif s.kind == ARC:
            piece = _arc_curve(plane, s, start, end)
        else:
            piece = _free_curve(free_curves, s, start, end)
        curve.Append(piece)
    return curve


# Main -----------------------------------------------------------------------


def _group(curves, keys, tol, angle_tol):
    """Groups planar inputs by key and plane; returns (groups, skipped)."""
    groups: list = []  # (key, plane, [input index])
    skipped, linear = [], []
    for i, curve in enumerate(curves):
        if curve is None:
            continue
        if curve.IsLinear(tol):
            linear.append(i)
            continue
        ok, plane = curve.TryGetPlane(tol)
        if not ok:
            skipped.append(i)
            continue
        plane = _group_plane(curve.PointAtStart, plane.ZAxis)
        for key, gplane, members in groups:
            if key == keys[i] and _same_plane(gplane, plane, tol, angle_tol):
                members.append(i)
                break
        else:
            groups.append((keys[i], plane, [i]))
    for i in linear:
        for key, gplane, members in groups:
            if key == keys[i] and _contains(gplane, curves[i], tol):
                members.append(i)
                break
        else:
            groups.append((keys[i], _line_plane(curves[i]), [i]))
    return groups, skipped


def clean_curves(
    curves: Sequence,
    keys: Sequence[Hashable],
    tol: float,
    max_angle_deg: float,
    angle_tol: float = math.radians(1.0),
) -> CleanResult:
    """Cleans a network of planar curves (see the module docstring).

    Args:
        curves: Input curves (``Rhino.Geometry.Curve``).
        keys: Group key per input; curves with different keys never interact.
        tol: Absolute tolerance.
        max_angle_deg: Maximum deviation from straight at junctions, degrees.
        angle_tol: Angle tolerance in radians for coplanarity.

    Returns:
        The cleaning result.
    """
    groups, skipped = _group(curves, keys, tol, angle_tol)
    result_curves, sources, unchanged = [], [], []
    removed_total = 0
    max_angle = math.radians(max_angle_deg)
    for _, plane, members in groups:
        pieces = [_Piece(p, i) for i in members for p in _explode(curves[i])]
        pieces, removed, touched = _remove_free_overlaps(pieces, tol)
        free_curves: list = []
        segments: list = []
        for piece in pieces:
            segments += _to_segments(piece.curve, piece.source, plane, tol, free_curves)
        before = Counter(segments)
        original = Counter(s.source for s in segments)
        segments = drop_slivers(segments, tol)
        segments, count = remove_overlaps(segments, tol)
        removed_total += removed + count
        touched |= {s.source for s in (before - Counter(segments))}
        touched |= {s.source for s in (Counter(segments) - before)}
        for chain in build_chains(segments, tol, max_angle):
            chain_sources = {segments[i].source for i, _ in chain.items}
            longest = max(chain.items, key=lambda item: segments[item[0]].length)
            source = segments[longest[0]].source
            parts = compact_chain(segments, chain, tol)
            if (
                len(chain_sources) == 1
                and source not in touched
                and len(chain.items) == original[source]
                and len(parts) == original[source]
                and chain.closed == curves[source].IsClosed
            ):
                unchanged.append(source)
                continue
            result_curves.append(_assemble(plane, parts, chain.closed, free_curves))
            sources.append(source)
    return CleanResult(result_curves, sources, unchanged, skipped, removed_total)

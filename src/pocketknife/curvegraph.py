"""Pure-Python curve network cleaning in 2D (no Rhino dependency).

Curves are reduced to segments (lines, arcs or free curves) in the plane
coordinates of their group. The functions here remove overlaps, fuse
endpoints into nodes, pair the straightest branches at each node, walk the
resulting chains and merge collinear lines and co-circular arcs inside them.
Free curves are opaque: only their endpoints and end tangents are used.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import NamedTuple

Point2 = tuple[float, float]
Vec2 = tuple[float, float]

LINE = "line"
ARC = "arc"
FREE = "free"


class Segment(NamedTuple):
    """One piece of a curve network.

    Attributes:
        kind: ``LINE``, ``ARC`` or ``FREE``.
        start: Start point.
        end: End point.
        t_start: Unit tangent at the start, pointing into the segment.
        t_end: Unit tangent at the end, pointing into the segment (the
            reversed derivative).
        length: Curve length.
        center: Arc center (arcs only).
        radius: Arc radius (arcs only).
        ccw: True if the arc runs counter-clockwise from start to end.
        source: Index of the input curve the segment comes from.
        start_angle: Arc start angle in radians (arcs only).
        sweep: Signed arc sweep in radians (arcs only).
    """

    kind: str
    start: Point2
    end: Point2
    t_start: Vec2
    t_end: Vec2
    length: float
    center: Point2 | None = None
    radius: float | None = None
    ccw: bool | None = None
    source: int = -1
    start_angle: float | None = None
    sweep: float | None = None


def _unit(x: float, y: float) -> Vec2:
    n = math.hypot(x, y)
    if n == 0.0:
        return (0.0, 0.0)
    return (x / n, y / n)


def _dist(a: Point2, b: Point2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def line_segment(start: Point2, end: Point2, source: int = -1) -> Segment:
    """Builds a line segment.

    Args:
        start: Start point.
        end: End point.
        source: Index of the input curve.

    Returns:
        The segment.
    """
    start = (float(start[0]), float(start[1]))
    end = (float(end[0]), float(end[1]))
    d = _unit(end[0] - start[0], end[1] - start[1])
    return Segment(
        LINE, start, end, d, (-d[0], -d[1]), _dist(start, end), source=source
    )


def arc_segment(
    center: Point2,
    radius: float,
    start_angle: float,
    sweep: float,
    source: int = -1,
) -> Segment:
    """Builds an arc segment.

    Args:
        center: Arc center.
        radius: Arc radius.
        start_angle: Angle of the start point, in radians.
        sweep: Signed sweep in radians; positive is counter-clockwise. A full
            circle has ``abs(sweep) == 2 * pi`` and ``start == end``.
        source: Index of the input curve.

    Returns:
        The segment.
    """
    cx, cy = float(center[0]), float(center[1])
    end_angle = start_angle + sweep
    start = (cx + radius * math.cos(start_angle), cy + radius * math.sin(start_angle))
    end = (cx + radius * math.cos(end_angle), cy + radius * math.sin(end_angle))
    sign = 1.0 if sweep >= 0 else -1.0
    t_start = (-sign * math.sin(start_angle), sign * math.cos(start_angle))
    t_end = (sign * math.sin(end_angle), -sign * math.cos(end_angle))
    return Segment(
        ARC,
        start,
        end,
        t_start,
        t_end,
        abs(sweep) * radius,
        center=(cx, cy),
        radius=float(radius),
        ccw=sweep >= 0,
        source=source,
        start_angle=float(start_angle),
        sweep=float(sweep),
    )


def reversed_segment(segment: Segment) -> Segment:
    """Returns the same segment running the other way.

    Args:
        segment: Segment to reverse.

    Returns:
        The reversed segment.
    """
    if segment.kind == ARC:
        return arc_segment(
            segment.center,
            segment.radius,
            segment.start_angle + segment.sweep,
            -segment.sweep,
            segment.source,
        )
    return segment._replace(
        start=segment.end,
        end=segment.start,
        t_start=segment.t_end,
        t_end=segment.t_start,
    )


def drop_slivers(segments: Sequence[Segment], tol: float) -> list[Segment]:
    """Removes segments not longer than the tolerance.

    Args:
        segments: Input segments.
        tol: Absolute tolerance.

    Returns:
        Segments longer than ``tol``.
    """
    return [s for s in segments if s.length > tol]


def fuse_endpoints(points: Sequence[Point2], tol: float) -> list[int]:
    """Groups points closer than the tolerance into nodes, without chaining.

    Points are processed in order. A point joins the first existing cluster
    whose members are all within ``tol`` of it, so every cluster has a
    diameter of at most ``tol``.

    Args:
        points: Endpoints.
        tol: Absolute tolerance.

    Returns:
        A node id per point, numbered from 0 in order of first appearance.
    """
    cell = tol if tol > 0 else 1e-12
    grid: dict[tuple[int, int], list[int]] = {}
    clusters: list[list[Point2]] = []
    ids: list[int] = []
    for p in points:
        ix, iy = math.floor(p[0] / cell), math.floor(p[1] / cell)
        found = -1
        candidates = sorted(
            {
                c
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                for c in grid.get((ix + dx, iy + dy), ())
            }
        )
        for c in candidates:
            if all(_dist(p, q) <= tol for q in clusters[c]):
                found = c
                break
        if found < 0:
            found = len(clusters)
            clusters.append([])
        clusters[found].append(p)
        bucket = grid.setdefault((ix, iy), [])
        if found not in bucket:
            bucket.append(found)
        ids.append(found)
    return ids

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


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _line_distance(p: Point2, a: Segment) -> float:
    d = a.t_start
    return abs((p[0] - a.start[0]) * d[1] - (p[1] - a.start[1]) * d[0])


def _lines_overlap(a: Segment, b: Segment, tol: float) -> bool:
    if any(_line_distance(p, a) > tol for p in (b.start, b.end)):
        return False
    if any(_line_distance(p, b) > tol for p in (a.start, a.end)):
        return False
    d = a.t_start

    def t(p: Point2) -> float:
        return (p[0] - a.start[0]) * d[0] + (p[1] - a.start[1]) * d[1]

    lo, hi = sorted((t(b.start), t(b.end)))
    return min(hi, a.length) - max(lo, 0.0) > tol


_ANGLE_BUCKET = 0.01


def _line_groups(lines: list[int], segments: Sequence[Segment], tol: float):
    """Unions indices of lines that overlap on a common support line."""
    uf = _UnionFind(len(segments))
    buckets: dict[int, list[int]] = {}
    for i in lines:
        d = segments[i].t_start
        theta = math.atan2(d[1], d[0]) % math.pi
        buckets.setdefault(int(theta / _ANGLE_BUCKET), []).append(i)
    count = int(math.pi / _ANGLE_BUCKET) + 1
    for key, members in buckets.items():
        theta0 = (key + 0.5) * _ANGLE_BUCKET
        n0 = (-math.sin(theta0), math.cos(theta0))
        neighbours = list(members)
        for other in ((key + 1) % count,):
            if other != key:
                neighbours += buckets.get(other, [])
        if key == 0:
            # Angles near pi wrap around to 0.
            neighbours += buckets.get(count - 1, [])
        intervals = []
        for i in neighbours:
            s = segments[i]
            a = s.start[0] * n0[0] + s.start[1] * n0[1]
            b = s.end[0] * n0[0] + s.end[1] * n0[1]
            intervals.append((min(a, b) - tol, max(a, b) + tol, i))
        intervals.sort()
        active: list[tuple[float, int]] = []
        for lo, hi, i in intervals:
            active = [(h, j) for h, j in active if h >= lo]
            for _, j in active:
                if uf.find(i) != uf.find(j) and _lines_overlap(
                    segments[i], segments[j], tol
                ):
                    uf.union(i, j)
            active.append((hi, i))
    groups: dict[int, list[int]] = {}
    for i in lines:
        groups.setdefault(uf.find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def _split_lines(
    group: list[int], segments: Sequence[Segment], tol: float
) -> tuple[list[Segment], int]:
    ref = max(group, key=lambda i: (segments[i].length, -i))
    origin, d = segments[ref].start, segments[ref].t_start

    def t(p: Point2) -> float:
        return (p[0] - origin[0]) * d[0] + (p[1] - origin[1]) * d[1]

    breaks: list[tuple[float, Point2]] = []
    for i in group:
        for p in (segments[i].start, segments[i].end):
            breaks.append((t(p), p))
    breaks.sort()
    fused: list[tuple[float, Point2]] = []
    for tp, p in breaks:
        if not fused or tp - fused[-1][0] > tol:
            fused.append((tp, p))
    spans = [(min(t(segments[i].start), t(segments[i].end)), i) for i in group]
    spans = [(lo, lo + segments[i].length, i) for lo, i in spans]
    pieces: list[Segment] = []
    removed = 0
    for (ta, pa), (tb, pb) in zip(fused, fused[1:]):
        mid = 0.5 * (ta + tb)
        covering = [i for lo, hi, i in spans if lo < mid < hi]
        if not covering:
            continue
        removed += len(covering) - 1
        owner = max(covering, key=lambda i: (segments[i].length, -i))
        pieces.append(line_segment(pa, pb, segments[owner].source))
    return pieces, removed


def _arc_groups(arcs: list[int], segments: Sequence[Segment], tol: float):
    uf = _UnionFind(len(segments))
    cell = max(tol, 1e-12) * 4
    grid: dict[tuple[int, int, int], list[int]] = {}
    for i in arcs:
        s = segments[i]
        key = (
            math.floor(s.center[0] / cell),
            math.floor(s.center[1] / cell),
            math.floor(s.radius / cell),
        )
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dr), ()):
                        o = segments[j]
                        if (
                            _dist(s.center, o.center) <= tol
                            and abs(s.radius - o.radius) <= tol
                            and _arcs_overlap(s, o, tol)
                        ):
                            uf.union(i, j)
        grid.setdefault(key, []).append(i)
    groups: dict[int, list[int]] = {}
    for i in arcs:
        groups.setdefault(uf.find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


_TWO_PI = 2.0 * math.pi


def _ccw_interval(s: Segment) -> tuple[float, float]:
    """Start angle in [0, 2pi) and positive extent of an arc, run CCW."""
    if s.sweep >= 0:
        return s.start_angle % _TWO_PI, s.sweep
    return (s.start_angle + s.sweep) % _TWO_PI, -s.sweep


def _in_interval(angle: float, start: float, extent: float) -> bool:
    return (angle - start) % _TWO_PI < extent


def _arcs_overlap(a: Segment, b: Segment, tol: float) -> bool:
    sa, ea = _ccw_interval(a)
    sb, eb = _ccw_interval(b)
    margin = tol / a.radius
    # Overlap if one interval contains a point of the other beyond the margin.
    for start, extent, s2, e2 in ((sa, ea, sb, eb), (sb, eb, sa, ea)):
        lo, hi = s2 + margin, s2 + e2 - margin
        if hi <= lo:
            continue
        for probe in (lo, hi, 0.5 * (lo + hi)):
            if _in_interval(probe, start, extent - margin) and (
                (probe - start) % _TWO_PI > margin
            ):
                return True
    return False


def _split_arcs(
    group: list[int], segments: Sequence[Segment], tol: float
) -> tuple[list[Segment], int]:
    ref = segments[max(group, key=lambda i: (segments[i].length, -i))]
    center, radius = ref.center, ref.radius
    margin = tol / radius
    angles = []
    for i in group:
        start, extent = _ccw_interval(segments[i])
        angles.append(start)
        angles.append((start + extent) % _TWO_PI)
    angles.sort()
    fused: list[float] = []
    for a in angles:
        if not fused or a - fused[-1] > margin:
            fused.append(a)
    if len(fused) > 1 and fused[0] + _TWO_PI - fused[-1] <= margin:
        fused.pop()
    intervals = [(_ccw_interval(segments[i]), i) for i in group]
    pieces: list[Segment] = []
    removed = 0
    for k, a in enumerate(fused):
        b = fused[(k + 1) % len(fused)]
        extent = (b - a) % _TWO_PI or _TWO_PI
        mid = a + 0.5 * extent
        covering = [i for (s, e), i in intervals if _in_interval(mid, s, e)]
        if not covering:
            continue
        removed += len(covering) - 1
        owner = max(covering, key=lambda i: (segments[i].length, -i))
        pieces.append(arc_segment(center, radius, a, extent, segments[owner].source))
    return pieces, removed


def remove_overlaps(
    segments: Sequence[Segment], tol: float
) -> tuple[list[Segment], int]:
    """Draws every overlapping stretch of lines and arcs only once.

    Lines on a common support line and arcs on a common circle that overlap
    are replaced by the pieces of their union, split at every original
    endpoint so no node is lost. Each piece takes the ``source`` of the
    longest original segment covering it. Segments that overlap nothing,
    and all ``FREE`` segments, are returned unchanged and in order.

    Args:
        segments: Input segments.
        tol: Absolute tolerance.

    Returns:
        ``(segments, removed)``: the cleaned segments and the number of
        duplicated stretches removed.
    """
    lines = [i for i, s in enumerate(segments) if s.kind == LINE]
    arcs = [i for i, s in enumerate(segments) if s.kind == ARC]
    groups = [(g, _split_lines) for g in _line_groups(lines, segments, tol)]
    groups += [(g, _split_arcs) for g in _arc_groups(arcs, segments, tol)]
    replaced: set[int] = set()
    added: list[Segment] = []
    removed = 0
    for group, split in groups:
        pieces, count = split(group, segments, tol)
        if count == 0:
            continue
        replaced.update(group)
        added += pieces
        removed += count
    kept = [s for i, s in enumerate(segments) if i not in replaced]
    return kept + added, removed

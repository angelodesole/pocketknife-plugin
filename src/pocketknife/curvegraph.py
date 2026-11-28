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
        ref: Caller-defined reference, e.g. the index of the original free
            curve. Kept by ``reversed_segment``.
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
    ref: int = -1


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


def _sweep_pairs(items: list[tuple[float, float, int]]):
    """Yields index pairs whose ``(lo, hi)`` intervals overlap."""
    items.sort()
    active: list[tuple[float, int]] = []
    for lo, hi, i in items:
        active = [(h, j) for h, j in active if h >= lo]
        for _, j in active:
            yield i, j
        active.append((hi, i))


def _clusters(items: list[tuple[float, float, int]]) -> list[list[int]]:
    """Connected runs of overlapping ``(lo, hi)`` intervals."""
    items.sort()
    out: list[list[int]] = []
    reach = -math.inf
    for lo, hi, i in items:
        if lo > reach:
            out.append([])
        out[-1].append(i)
        reach = max(reach, hi)
    return out


def _angle_clusters(lines: list[int], segments: Sequence[Segment], tol: float):
    """Groups lines whose directions may agree within their uncertainty.

    A line of length ``L`` has a direction uncertain by about ``2 tol / L``.
    Directions are taken modulo pi; a cluster can wrap around pi.

    Returns:
        ``(reference angle, members)`` per cluster; the reference is the
        direction of the longest member.
    """
    items = []
    for i in lines:
        s = segments[i]
        theta = math.atan2(s.t_start[1], s.t_start[0]) % math.pi
        items.append((theta, min(math.pi / 2, 2.0 * tol / s.length), i))
    items.sort()
    clusters: list[list[tuple[float, float, int]]] = []
    reach = -math.inf
    for theta, spread, i in items:
        if theta - spread > reach:
            clusters.append([])
        clusters[-1].append((theta, spread, i))
        reach = max(reach, theta + spread)
    if len(clusters) > 1:
        first_low = min(theta - spread for theta, spread, _ in clusters[0])
        if reach - math.pi >= first_low:
            clusters[0] += clusters.pop()
    out = []
    for members in clusters:
        _, _, ref = max(members, key=lambda m: (segments[m[2]].length, -m[2]))
        d = segments[ref].t_start
        out.append((math.atan2(d[1], d[0]), [m[2] for m in members]))
    return out


def _line_groups(lines: list[int], segments: Sequence[Segment], tol: float):
    """Unions indices of lines that overlap on a common support line.

    Lines are clustered by direction, then by their extent across the
    cluster direction, then swept along it, so long runs of collinear
    fragments and dense parallel grids both stay near linear.
    """
    uf = _UnionFind(len(segments))
    for theta0, members in _angle_clusters(lines, segments, tol):
        if len(members) < 2:
            continue
        d0 = (math.cos(theta0), math.sin(theta0))
        n0 = (-d0[1], d0[0])

        def extent(i: int, axis: Vec2) -> tuple[float, float, int]:
            s = segments[i]
            a = s.start[0] * axis[0] + s.start[1] * axis[1]
            b = s.end[0] * axis[0] + s.end[1] * axis[1]
            return (min(a, b) - tol, max(a, b) + tol, i)

        for cluster in _clusters([extent(i, n0) for i in members]):
            if len(cluster) < 2:
                continue
            for i, j in _sweep_pairs([extent(i, d0) for i in cluster]):
                if uf.find(i) != uf.find(j) and _lines_overlap(
                    segments[i], segments[j], tol
                ):
                    uf.union(i, j)
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
    spans = sorted((min(t(segments[i].start), t(segments[i].end)), i) for i in group)
    pieces: list[Segment] = []
    removed = 0
    active: list[tuple[float, int]] = []
    k = 0
    for (ta, pa), (tb, pb) in zip(fused, fused[1:]):
        mid = 0.5 * (ta + tb)
        while k < len(spans) and spans[k][0] < mid:
            lo, i = spans[k]
            active.append((lo + segments[i].length, i))
            k += 1
        active = [(hi, i) for hi, i in active if hi > mid]
        if not active:
            continue
        removed += len(active) - 1
        owner = max((i for _, i in active), key=lambda i: (segments[i].length, -i))
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


class Chain(NamedTuple):
    """An ordered run of segments that becomes one output curve.

    Attributes:
        items: ``(segment index, reversed)`` pairs, in order along the curve.
        closed: True if the chain ends where it starts.
    """

    items: list[tuple[int, bool]]
    closed: bool


def _deviation(a: Vec2, b: Vec2) -> float:
    """Angle between ``a`` and the reverse of ``b`` (0 = straight on)."""
    dot = -(a[0] * b[0] + a[1] * b[1])
    return math.acos(max(-1.0, min(1.0, dot)))


def _pair_ends(
    segments: Sequence[Segment], tol: float, max_angle: float
) -> tuple[dict[int, int], list[int]]:
    """Pairs segment ends at each node. Ends are numbered ``2 * i + side``.

    Returns:
        The pairing, and the node id of every end.
    """
    points = [p for s in segments for p in (s.start, s.end)]
    node_ids = fuse_endpoints(points, tol)
    nodes: dict[int, list[int]] = {}
    for end, node in enumerate(node_ids):
        nodes.setdefault(node, []).append(end)

    def tangent(end: int) -> Vec2:
        s = segments[end // 2]
        return s.t_end if end % 2 else s.t_start

    pairs: dict[int, int] = {}
    for ends in nodes.values():
        if len(ends) == 2:
            a, b = ends
            pairs[a], pairs[b] = b, a
            continue
        used: set[int] = set()
        # A closed segment (both ends at this node) stays a loop of its own.
        for a in ends:
            if a % 2 == 0 and a + 1 in ends:
                used.update((a, a + 1))
                pairs[a], pairs[a + 1] = a + 1, a
        candidates = sorted(
            (round(_deviation(tangent(a), tangent(b)), 9), a, b)
            for k, a in enumerate(ends)
            for b in ends[k + 1 :]
        )
        for dev, a, b in candidates:
            if dev > max_angle:
                break
            if a in used or b in used:
                continue
            used.update((a, b))
            pairs[a], pairs[b] = b, a
    return pairs, node_ids


def build_chains(
    segments: Sequence[Segment],
    tol: float,
    max_angle: float,
    split_touches: bool = False,
) -> list[Chain]:
    """Joins segments into chains following the straightest continuation.

    At a node with two branches the branches are always joined. At a node
    with three or more, the pair of branches closest to straight is joined
    first, as long as its deviation is within ``max_angle``, and so on.
    Branches left without a partner end at the node.

    Args:
        segments: Segments, already free of overlaps.
        tol: Absolute tolerance used to fuse endpoints.
        max_angle: Maximum deviation from straight at junctions, in radians.
        split_touches: If True, a chain that passes the same node twice is
            split there: the part between the two visits becomes its own
            closed chain, repeatedly, until no chain repeats a node.

    Returns:
        Open chains (walked from their free ends, in segment order), then
        closed chains.
    """
    pairs, node_ids = _pair_ends(segments, tol, max_angle)
    visited = [False] * len(segments)
    chains: list[Chain] = []

    def walk(first: int, entry_side: int) -> Chain:
        items = []
        seg, side = first, entry_side
        while True:
            visited[seg] = True
            items.append((seg, side == 1))
            partner = pairs.get(2 * seg + 1 - side)
            if partner is None:
                return Chain(items, False)
            seg, side = partner // 2, partner % 2
            if seg == first and side == entry_side:
                return Chain(items, True)
            if visited[seg]:
                return Chain(items, False)

    for end in range(2 * len(segments)):
        if end not in pairs and not visited[end // 2]:
            chains.append(walk(end // 2, end % 2))
    for seg in range(len(segments)):
        if not visited[seg]:
            chains.append(walk(seg, 0))
    if not split_touches:
        return chains

    def split(chain: Chain) -> tuple[list[Chain], list[Chain]]:
        first_seg, first_rev = chain.items[0]
        stack_nodes = [node_ids[2 * first_seg + (1 if first_rev else 0)]]
        stack_items: list[tuple[int, bool]] = []
        loops: list[Chain] = []
        for item in chain.items:
            seg, rev = item
            stack_items.append(item)
            node = node_ids[2 * seg + (0 if rev else 1)]
            if node in stack_nodes:
                at = stack_nodes.index(node)
                loops.append(Chain(stack_items[at:], True))
                del stack_items[at:]
                del stack_nodes[at + 1 :]
            else:
                stack_nodes.append(node)
        rest = [Chain(stack_items, False)] if stack_items else []
        return rest, loops

    opened: list[Chain] = []
    closed: list[Chain] = []
    for chain in chains:
        rest, loops = split(chain)
        opened.extend(rest)
        closed.extend(loops)
    return opened + closed


def _segment_point_distance(p: Point2, a: Point2, b: Point2) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return _dist(p, a)
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _simplify_lines(run: list[Segment], tol: float) -> list[Segment]:
    """Fewest lines through a run of lines keeping every vertex within tol.

    Douglas-Peucker on the run's vertices: a stretch becomes one line when
    every intermediate vertex is within ``tol`` of it and no piece of the
    stretch runs backwards along it.
    """
    points = [run[0].start] + [s.end for s in run]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        a, b = points[first], points[last]
        d = _unit(b[0] - a[0], b[1] - a[1])
        worst, split = -1.0, -1
        for k in range(first + 1, last):
            dist = _segment_point_distance(points[k], a, b)
            back = run[k - 1].t_start[0] * d[0] + run[k - 1].t_start[1] * d[1] <= 0
            if back or _dist(a, b) <= tol:
                dist = math.inf
            if dist > worst:
                worst, split = dist, k
        if run[last - 1].t_start[0] * d[0] + run[last - 1].t_start[1] * d[1] <= 0:
            worst, split = math.inf, last - 1
        if worst > tol:
            keep[split] = True
            stack += [(first, split), (split, last)]
    out = []
    first = 0
    for k in range(1, len(points)):
        if keep[k]:
            pieces = run[first:k]
            owner = max(pieces, key=lambda s: s.length)
            out.append(
                pieces[0]
                if len(pieces) == 1
                else line_segment(points[first], points[k], owner.source)
            )
            first = k
    return out


def _simplify_arcs(run: list[Segment], tol: float) -> list[Segment]:
    """Merges consecutive co-circular arcs, keeping every vertex within tol."""
    out: list[Segment] = []
    group: list[Segment] = []
    sweep = 0.0

    def flush() -> None:
        if not group:
            return
        if len(group) == 1:
            out.append(group[0])
            return
        first = group[0]
        total = sweep
        if abs(abs(total) - _TWO_PI) <= tol / first.radius:
            total = math.copysign(_TWO_PI, total)
        owner = max(group, key=lambda s: s.length)
        out.append(
            arc_segment(
                first.center, first.radius, first.start_angle, total, owner.source
            )
        )

    for s in run:
        if group:
            first = group[0]
            end_angle = first.start_angle + sweep + s.sweep
            end = (
                first.center[0] + first.radius * math.cos(end_angle),
                first.center[1] + first.radius * math.sin(end_angle),
            )
            fits = (
                s.ccw == first.ccw
                and _dist(s.center, first.center) <= tol
                and abs(s.radius - first.radius) <= tol
                and abs(_dist(s.start, first.center) - first.radius) <= tol
                and _dist(end, s.end) <= tol
                and abs(sweep + s.sweep) <= _TWO_PI + tol / first.radius
            )
            if fits:
                group.append(s)
                sweep += s.sweep
                continue
            flush()
        group, sweep = [s], s.sweep
    flush()
    return out


def _compact(oriented: list[Segment], tol: float) -> list[Segment]:
    """Simplifies each run of consecutive lines and of consecutive arcs."""
    out: list[Segment] = []
    k = 0
    while k < len(oriented):
        kind = oriented[k].kind
        end = k + 1
        if kind != FREE:
            while end < len(oriented) and oriented[end].kind == kind:
                end += 1
        run = oriented[k:end]
        if kind == LINE:
            out += _simplify_lines(run, tol)
        elif kind == ARC:
            out += _simplify_arcs(run, tol)
        else:
            out += run
        k = end
    return out


def compact_chain(
    segments: Sequence[Segment], chain: Chain, tol: float
) -> list[Segment]:
    """Orients the chain's segments and merges mergeable neighbours.

    Consecutive lines merge into one line when every intermediate vertex
    stays within ``tol`` of it. Consecutive arcs merge when they share center,
    radius and direction within ``tol``. A closed chain also merges across its
    seam. ``FREE`` segments never merge. A merged segment keeps the ``source``
    of its longest piece.

    Args:
        segments: All segments the chain indexes.
        chain: Chain from ``build_chains``.
        tol: Absolute tolerance.

    Returns:
        The segments of the output curve, in order and oriented.
    """
    oriented = [
        reversed_segment(segments[i]) if rev else segments[i] for i, rev in chain.items
    ]
    out = _compact(oriented, tol)
    if chain.closed and len(out) > 1 and out[0].kind == out[-1].kind != FREE:
        if len(_compact([out[-1], out[0]], tol)) == 1:
            # The seam falls inside a run: restart the loop where the last
            # output piece starts and simplify again with all its vertices.
            k = min(
                range(len(oriented)),
                key=lambda j: _dist(oriented[j].start, out[-1].start),
            )
            out = _compact(oriented[k:] + oriented[:k], tol)
    return out

"""Pure-Python 2D geometry utilities (no Rhino dependency).

Points are ``(x, y)`` tuples. Every function here is unit-tested with pytest
outside Rhino, so the algorithms can be checked in CI.
"""

from __future__ import annotations

import heapq
import itertools
import math
from collections.abc import Sequence
from typing import NamedTuple

Point2 = tuple[float, float]
Ring = Sequence[Point2]

AREA = "Area"
PERIMETER = "Perimeter"


class Rect2D(NamedTuple):
    """Oriented rectangle in the XY plane.

    Attributes:
        center: Rectangle center.
        angle: Direction of the rectangle local X axis, in radians.
        width: Size along the local X axis.
        height: Size along the local Y axis.
    """

    center: Point2
    angle: float
    width: float
    height: float


def _cross(o: Point2, a: Point2, b: Point2) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points: Sequence[Point2]) -> list[Point2]:
    """Computes the convex hull with Andrew's monotone chain algorithm.

    Args:
        points: Input points.

    Returns:
        Hull vertices in counter-clockwise order, without repeating the first one.
    """
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    lower: list[Point2] = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point2] = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_bounding_rect(points: Sequence[Point2], metric: str = AREA) -> Rect2D:
    """Finds the minimum bounding rectangle of a point set.

    The optimal rectangle has one side collinear with a convex hull edge, so
    every hull edge direction is tested (rotating calipers principle).

    Args:
        points: Input points, at least one.
        metric: ``AREA`` or ``PERIMETER``, the quantity to minimize.

    Returns:
        The minimum rectangle.

    Raises:
        ValueError: If ``points`` is empty or ``metric`` is unknown.
    """
    if metric not in (AREA, PERIMETER):
        raise ValueError(f"Unknown metric: {metric}")
    hull = convex_hull(points)
    if not hull:
        raise ValueError("At least one point is required.")
    if len(hull) == 1:
        return Rect2D(hull[0], 0.0, 0.0, 0.0)

    best: tuple[float, Rect2D] | None = None
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length == 0.0:
            continue
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        vx, vy = -uy, ux
        s_values = [p[0] * ux + p[1] * uy for p in hull]
        t_values = [p[0] * vx + p[1] * vy for p in hull]
        s0, s1 = min(s_values), max(s_values)
        t0, t1 = min(t_values), max(t_values)
        w, h = s1 - s0, t1 - t0
        score = w * h if metric == AREA else w + h
        if best is None or score < best[0] - 1e-12:
            sc, tc = (s0 + s1) / 2.0, (t0 + t1) / 2.0
            center = (sc * ux + tc * vx, sc * uy + tc * vy)
            best = (score, Rect2D(center, math.atan2(uy, ux), w, h))
    assert best is not None
    return best[1]


def rect_corners(rect: Rect2D) -> list[Point2]:
    """Returns the four corners of a rectangle, counter-clockwise."""
    cx, cy = rect.center
    ux, uy = math.cos(rect.angle), math.sin(rect.angle)
    vx, vy = -uy, ux
    hw, hh = rect.width / 2.0, rect.height / 2.0
    return [
        (cx + sx * hw * ux + sy * hh * vx, cy + sx * hw * uy + sy * hh * vy)
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]


def alignment_rotation(rect: Rect2D, axis: str = "X") -> float:
    """Computes the smallest rotation aligning the rectangle long side to an axis.

    Args:
        rect: Rectangle to align.
        axis: ``"X"`` or ``"Y"``, the world axis for the long side.

    Returns:
        Rotation angle in radians, in the range (-pi/2, pi/2].
    """
    long_angle = rect.angle if rect.width >= rect.height else rect.angle + math.pi / 2
    target = 0.0 if axis.upper() == "X" else math.pi / 2
    rotation = target - long_angle
    # A rectangle is symmetric under a 180 degree turn: keep the smallest turn.
    rotation = (rotation + math.pi / 2) % math.pi - math.pi / 2
    if math.isclose(rotation, -math.pi / 2):
        rotation = math.pi / 2
    return rotation


def polygon_area(ring: Ring) -> float:
    """Returns the signed area of a ring (positive if counter-clockwise)."""
    area = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return area / 2.0


def point_in_polygon(point: Point2, ring: Ring) -> bool:
    """Tests whether a point lies inside a ring (even-odd rule)."""
    x, y = point
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segment_distance_sq(px: float, py: float, a: Point2, b: Point2) -> float:
    x, y = a
    dx, dy = b[0] - x, b[1] - y
    if dx != 0.0 or dy != 0.0:
        t = ((px - x) * dx + (py - y) * dy) / (dx * dx + dy * dy)
        if t > 1.0:
            x, y = b
        elif t > 0.0:
            x += dx * t
            y += dy * t
    dx, dy = px - x, py - y
    return dx * dx + dy * dy


def signed_distance(point: Point2, rings: Sequence[Ring]) -> float:
    """Distance from a point to a polygon boundary, positive inside.

    Args:
        point: Query point.
        rings: Outer ring followed by hole rings.

    Returns:
        Signed distance to the nearest boundary segment.
    """
    x, y = point
    inside = False
    min_sq = math.inf
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            a, b = ring[i], ring[j]
            if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (
                b[1] - a[1]
            ) + a[0]:
                inside = not inside
            min_sq = min(min_sq, _segment_distance_sq(x, y, a, b))
            j = i
    return (1.0 if inside else -1.0) * math.sqrt(min_sq)


def _centroid(ring: Ring) -> Point2:
    area = 0.0
    cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
        area += f * 3.0
    if area == 0.0:
        return ring[0]
    return (cx / area, cy / area)


def polylabel(
    rings: Sequence[Ring], precision: float | None = None, relative: float = 1e-3
) -> Point2:
    """Finds the pole of inaccessibility of a polygon.

    It is the interior point farthest from the boundary, so it is always inside
    the polygon (unlike the centroid). Iterative grid algorithm by Mapbox.

    Args:
        rings: Outer ring followed by hole rings. Rings must not repeat the
            first point at the end.
        precision: Absolute tolerance of the result. If None, it is
            ``relative`` times the largest bounding-box side.
        relative: Relative tolerance used when ``precision`` is None.

    Returns:
        The pole of inaccessibility.
    """
    outer = rings[0]
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    cell_size = min(width, height)
    if cell_size == 0.0:
        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
    if precision is None or precision <= 0.0:
        precision = max(width, height) * relative

    counter = itertools.count()
    heap: list[tuple[float, int, tuple[float, float, float, float]]] = []

    def make_cell(x: float, y: float, h: float) -> tuple[float, float, float, float]:
        d = signed_distance((x, y), rings)
        return (x, y, h, d)

    def push(cell: tuple[float, float, float, float]) -> None:
        x, y, h, d = cell
        heapq.heappush(heap, (-(d + h * math.sqrt(2.0)), next(counter), cell))

    h = cell_size / 2.0
    x = min_x
    while x < max_x:
        y = min_y
        while y < max_y:
            push(make_cell(x + h, y + h, h))
            y += cell_size
        x += cell_size

    cx, cy = _centroid(outer)
    best = make_cell(cx, cy, 0.0)
    bbox_cell = make_cell(min_x + width / 2.0, min_y + height / 2.0, 0.0)
    if bbox_cell[3] > best[3]:
        best = bbox_cell

    while heap:
        neg_max, _, cell = heapq.heappop(heap)
        if cell[3] > best[3]:
            best = cell
        if -neg_max - best[3] <= precision:
            continue
        x, y, h, _ = cell
        h /= 2.0
        for dx, dy in ((-h, -h), (h, -h), (-h, h), (h, h)):
            push(make_cell(x + dx, y + dy, h))
    return (best[0], best[1])


def group_loops_into_regions(loops: Sequence[Ring]) -> list[list[Ring]]:
    """Groups closed loops into regions made of an outer loop and its holes.

    Nesting depth decides the role: even depth is an outer boundary, odd depth
    is a hole of the smallest loop containing it. Islands inside holes become
    new regions.

    Args:
        loops: Closed loops, without repeating the first point.

    Returns:
        Regions ``[outer, hole, ...]`` sorted by outer area, largest first.
    """
    valid = [list(loop) for loop in loops if len(loop) >= 3]
    areas = [abs(polygon_area(loop)) for loop in valid]
    order = sorted(range(len(valid)), key=lambda k: -areas[k])
    depth: dict[int, int] = {}
    parent: dict[int, int | None] = {}
    for i in order:
        containers = [
            j
            for j in order
            if j != i
            and areas[j] > areas[i]
            and point_in_polygon(valid[i][0], valid[j])
        ]
        depth[i] = len(containers)
        parent[i] = min(containers, key=lambda k: areas[k]) if containers else None

    regions: dict[int, list[Ring]] = {}
    for i in order:
        if depth[i] % 2 == 0:
            regions[i] = [valid[i]]
    for i in order:
        if depth[i] % 2 == 1 and parent[i] in regions:
            regions[parent[i]].append(valid[i])
    return [regions[i] for i in order if i in regions]

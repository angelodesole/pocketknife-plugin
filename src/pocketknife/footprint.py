"""Pure-Python loop nesting for footprint outlines (no Rhino dependency).

The loops are the closed outlines of a union of shapes: they never cross and
share at most isolated points. Nesting tells islands (even depth) from holes
(odd depth), and ``keep_loops`` applies a minimum area filter in which a
dropped loop takes everything inside it along.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pocketknife.curvegraph import Point2

# Boxes covering more grid cells than this are scanned linearly instead.
_MAX_CELLS_PER_BOX = 64
_NUDGE = 1e-9


def _bbox(poly: Sequence[Point2]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _test_point(poly: Sequence[Point2], box: tuple[float, ...]) -> Point2:
    """Returns a point just inside the polygon, next to its longest edge."""
    n = len(poly)
    twice_area = 0.0
    best = -1.0
    best_i = 0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        twice_area += x0 * y1 - x1 * y0
        length = math.hypot(x1 - x0, y1 - y0)
        if length > best:
            best = length
            best_i = i
    x0, y0 = poly[best_i]
    x1, y1 = poly[(best_i + 1) % n]
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if best <= 0.0:
        return mx, my
    diagonal = math.hypot(box[2] - box[0], box[3] - box[1])
    sign = 1.0 if twice_area >= 0.0 else -1.0
    offset = _NUDGE * diagonal * sign / best
    return mx - (y1 - y0) * offset, my + (x1 - x0) * offset


def _contains(poly: Sequence[Point2], point: Point2) -> bool:
    """Even-odd ray casting."""
    px, py = point
    inside = False
    n = len(poly)
    x0, y0 = poly[-1]
    for i in range(n):
        x1, y1 = poly[i]
        if (y1 > py) != (y0 > py):
            x_cross = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < x_cross:
                inside = not inside
        x0, y0 = x1, y1
    return inside


def nest_loops(
    polygons: Sequence[Sequence[Point2]], areas: Sequence[float]
) -> list[int]:
    """Finds the parent of every loop.

    The parent of a loop is the smallest-area loop that contains a point just
    inside the loop's longest edge.

    Args:
        polygons: Loop vertices, each loop implicitly closed.
        areas: Absolute area of every loop.

    Returns:
        The parent index per loop, ``-1`` for a top-level loop.
    """
    count = len(polygons)
    boxes = [_bbox(p) for p in polygons]
    parents = [-1] * count
    if count < 2:
        return parents

    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_x = max(b[2] for b in boxes)
    max_y = max(b[3] for b in boxes)
    side = math.sqrt(max((max_x - min_x) * (max_y - min_y), 0.0) / count)
    if side <= 0.0:
        side = max(max_x - min_x, max_y - min_y, 1.0)

    def cell(value: float, origin: float) -> int:
        return int((value - origin) // side)

    grid: dict[tuple[int, int], list[int]] = {}
    large: list[int] = []
    for i, (bx0, by0, bx1, by1) in enumerate(boxes):
        i0, i1 = cell(bx0, min_x), cell(bx1, min_x)
        j0, j1 = cell(by0, min_y), cell(by1, min_y)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > _MAX_CELLS_PER_BOX:
            large.append(i)
            continue
        for a in range(i0, i1 + 1):
            for b in range(j0, j1 + 1):
                grid.setdefault((a, b), []).append(i)

    for i in range(count):
        point = _test_point(polygons[i], boxes[i])
        px, py = point
        key = (cell(px, min_x), cell(py, min_y))
        best = -1
        for j in grid.get(key, []) + large:
            if areas[j] <= areas[i] or (best >= 0 and areas[j] >= areas[best]):
                continue
            bx0, by0, bx1, by1 = boxes[j]
            if not (bx0 <= px <= bx1 and by0 <= py <= by1):
                continue
            if _contains(polygons[j], point):
                best = j
        parents[i] = best
    return parents


def loop_depths(parents: Sequence[int]) -> list[int]:
    """Returns the nesting depth of every loop (0 for top level).

    Even depth is an island, odd depth is a hole.
    """
    depths = [-1] * len(parents)
    for start in range(len(parents)):
        chain = []
        i = start
        while i >= 0 and depths[i] < 0:
            chain.append(i)
            i = parents[i]
        base = depths[i] if i >= 0 else -1
        for k, idx in enumerate(reversed(chain)):
            depths[idx] = base + 1 + k
    return depths


def keep_loops(
    parents: Sequence[int], areas: Sequence[float], min_area: float
) -> list[int]:
    """Applies the minimum area filter.

    A loop is dropped if its area is below ``min_area`` or any of its
    ancestors is dropped.

    Args:
        parents: Parent index per loop, ``-1`` for top level.
        areas: Absolute area of every loop.
        min_area: Minimum area to keep; zero or less keeps everything.

    Returns:
        The sorted indices of the loops kept.
    """
    if min_area <= 0.0:
        return list(range(len(parents)))
    kept: dict[int, bool] = {}
    for start in range(len(parents)):
        chain = []
        i = start
        while i >= 0 and i not in kept:
            chain.append(i)
            i = parents[i]
        alive = kept[i] if i >= 0 else True
        for idx in reversed(chain):
            alive = alive and areas[idx] >= min_area
            kept[idx] = alive
    return [i for i in range(len(parents)) if kept[i]]

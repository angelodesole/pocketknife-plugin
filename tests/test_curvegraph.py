"""Tests for pocketknife.curvegraph."""

import math
import random
import time

import pytest

from pocketknife.curvegraph import (
    ARC,
    FREE,
    LINE,
    Chain,
    Segment,
    arc_segment,
    build_chains,
    compact_chain,
    drop_slivers,
    fuse_endpoints,
    line_segment,
    remove_overlaps,
    reversed_segment,
)

TOL = 0.001
MAX_ANGLE = math.radians(15)


def grid(n, size, pieces, overhang=0.0):
    """n lines along X and n along Y, split at crossings and into pieces."""
    coords = [k * size / (n - 1) for k in range(n)]
    stops = sorted(
        {
            a + (b - a) * j / pieces
            for a, b in zip(coords, coords[1:])
            for j in range(pieces + 1)
        }
    )
    if overhang:
        stops = [-overhang] + stops + [size + overhang]
    segs = []
    for c in coords:
        for a, b in zip(stops, stops[1:]):
            segs.append(line_segment((a, c), (b, c)))
            segs.append(line_segment((c, a), (c, b)))
    return segs


def rectangle_edges(x, y, w, h):
    """Closed rectangle, bottom edge split at its middle."""
    pts = [(x, y), (x + w / 2, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return [line_segment(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]


def test_line_segment_tangents_point_inward():
    s = line_segment((0, 0), (2, 0))
    assert s.t_start == pytest.approx((1, 0))
    assert s.t_end == pytest.approx((-1, 0))
    assert s.length == pytest.approx(2)


def test_arc_segment_quarter_ccw():
    s = arc_segment((0, 0), 1.0, 0.0, math.pi / 2)
    assert s.start == pytest.approx((1, 0))
    assert s.end == pytest.approx((0, 1))
    assert s.t_start == pytest.approx((0, 1))
    assert s.t_end == pytest.approx((1, 0))
    assert s.length == pytest.approx(math.pi / 2)
    assert s.ccw


def test_arc_segment_clockwise_tangents():
    s = arc_segment((0, 0), 1.0, math.pi / 2, -math.pi / 2)
    assert s.start == pytest.approx((0, 1))
    assert s.end == pytest.approx((1, 0))
    assert s.t_start == pytest.approx((1, 0))
    assert s.t_end == pytest.approx((0, 1))
    assert not s.ccw


def test_drop_slivers():
    segs = [line_segment((0, 0), (1, 0)), line_segment((1, 0), (1.0005, 0))]
    assert drop_slivers(segs, TOL) == segs[:1]


def test_fuse_endpoints_within_tolerance():
    ids = fuse_endpoints([(0, 0), (0.0004, 0), (5, 5), (5, 5.0003)], TOL)
    assert ids[0] == ids[1]
    assert ids[2] == ids[3]
    assert ids[0] != ids[2]


def test_fuse_endpoints_no_chaining():
    # 0 - 0.0008 - 0.0016: neighbours within tol, cluster diameter beyond it.
    ids = fuse_endpoints([(0, 0), (0.0008, 0), (0.0016, 0)], TOL)
    assert len(set(ids)) >= 2


def _total_length(segments):
    return sum(s.length for s in segments)


def test_exact_duplicate_removed():
    a = line_segment((0, 0), (4, 0), source=0)
    b = line_segment((4, 0), (0, 0), source=1)
    out, n = remove_overlaps([a, b], TOL)
    assert _total_length(out) == pytest.approx(4)
    assert n == 1


def test_partial_overlap_drawn_once_and_endpoints_kept():
    segs = [line_segment((0, 0), (3, 0)), line_segment((2, 0), (5, 0))]
    out, n = remove_overlaps(segs, TOL)
    assert _total_length(out) == pytest.approx(5)
    assert n == 1
    xs = sorted({round(p[0], 9) for s in out for p in (s.start, s.end)})
    assert xs == pytest.approx([0, 2, 3, 5])


def test_overlap_keeps_source_of_longer_original():
    short = line_segment((1, 0), (2, 0), source=7)
    long = line_segment((0, 0), (5, 0), source=3)
    out, _ = remove_overlaps([short, long], TOL)
    assert {s.source for s in out} == {3}


def test_parallel_lines_beyond_tolerance_kept():
    segs = [line_segment((0, 0), (3, 0)), line_segment((0, 0.01), (3, 0.01))]
    out, n = remove_overlaps(segs, TOL)
    assert out == segs
    assert n == 0


def test_collinear_touching_lines_untouched():
    segs = [line_segment((0, 0), (1, 0)), line_segment((1, 0), (2, 0))]
    out, n = remove_overlaps(segs, TOL)
    assert out == segs
    assert n == 0


def test_arc_overlap():
    a = arc_segment((0, 0), 2, 0, math.pi)
    b = arc_segment((0, 0), 2, math.pi / 2, math.pi)
    out, n = remove_overlaps([a, b], TOL)
    assert _total_length(out) == pytest.approx(2 * 1.5 * math.pi)
    assert n == 1


def test_arc_duplicate_of_full_circle():
    a = arc_segment((0, 0), 1, 0, 2 * math.pi)
    b = arc_segment((0, 0), 1, 1.0, 2 * math.pi)
    out, n = remove_overlaps([a, b], TOL)
    assert _total_length(out) == pytest.approx(2 * math.pi)
    assert n >= 1


def test_line_and_arc_sharing_endpoints_not_overlapping():
    segs = [line_segment((-1, 0), (1, 0)), arc_segment((0, 0), 1, 0, math.pi)]
    out, n = remove_overlaps(segs, TOL)
    assert out == segs
    assert n == 0


def test_overlap_scales():
    rng = random.Random(1)
    segs = [
        line_segment(
            (rng.uniform(0, 1000), rng.uniform(0, 1000)),
            (rng.uniform(0, 1000), rng.uniform(0, 1000)),
        )
        for _ in range(2000)
    ]
    start = time.perf_counter()
    remove_overlaps(segs, TOL)
    assert time.perf_counter() - start < 2.0


def test_overlap_scales_on_dense_grid():
    segs = [line_segment((0, y), (1000, y)) for y in range(1000)]
    segs += [line_segment((x, 0), (x, 1000)) for x in range(1000)]
    start = time.perf_counter()
    out, n = remove_overlaps(segs, TOL)
    assert time.perf_counter() - start < 2.0
    assert n == 0


def _shape(chains):
    return sorted((c.closed, len(c.items)) for c in chains)


def test_grid_with_overhang_joins_along_x_and_y():
    chains = build_chains(grid(3, 10.0, 4, overhang=1.0), TOL, MAX_ANGLE)
    assert len(chains) == 6
    assert not any(c.closed for c in chains)


def test_grid_outline_closed_and_inner_lines_separate():
    chains = build_chains(grid(3, 10.0, 4), TOL, MAX_ANGLE)
    assert _shape(chains) == [(False, 8), (False, 8), (True, 32)]


def test_outline_not_joined_to_inner_t():
    segs = rectangle_edges(0, 0, 10, 6) + [line_segment((5, 0), (5, 3))]
    chains = build_chains(segs, TOL, MAX_ANGLE)
    assert _shape(chains) == [(False, 1), (True, 5)]


def test_cross_gives_two_straight_curves():
    segs = [
        line_segment((0, 0), (1, 0)),
        line_segment((1, 0), (2, 0)),
        line_segment((1, -1), (1, 0)),
        line_segment((1, 0), (1, 1)),
    ]
    chains = build_chains(segs, TOL, MAX_ANGLE)
    assert _shape(chains) == [(False, 2), (False, 2)]
    for c in chains:
        (i, _), (j, _) = c.items
        assert {i, j} in ({0, 1}, {2, 3})


def test_y_junction_splits():
    segs = [
        line_segment((0, 0), (math.cos(a), math.sin(a)))
        for a in (0, 2 * math.pi / 3, 4 * math.pi / 3)
    ]
    assert len(build_chains(segs, TOL, MAX_ANGLE)) == 3


def test_chain_items_are_oriented():
    segs = [line_segment((1, 0), (0, 0)), line_segment((1, 0), (2, 0))]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    assert chain.items == [(0, True), (1, False)]
    assert not chain.closed


def test_two_arcs_make_closed_circle():
    segs = [
        arc_segment((0, 0), 1, 0, math.pi),
        arc_segment((0, 0), 1, math.pi, math.pi),
    ]
    (c,) = build_chains(segs, TOL, MAX_ANGLE)
    assert c.closed
    assert len(c.items) == 2


def test_single_closed_segment_is_closed_chain():
    (c,) = build_chains([arc_segment((0, 0), 1, 0, 2 * math.pi)], TOL, MAX_ANGLE)
    assert c.closed
    assert c.items == [(0, False)]


def test_build_chains_is_deterministic():
    segs = grid(4, 9.0, 2)
    assert build_chains(segs, TOL, MAX_ANGLE) == build_chains(segs, TOL, MAX_ANGLE)


def _point_line_distance(p, s):
    ax, ay = s.start
    dx, dy = s.end[0] - ax, s.end[1] - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def test_forty_collinear_become_one_line():
    segs = [line_segment((i, 0), (i + 1, 0)) for i in range(40)]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    (line,) = compact_chain(segs, chain, TOL)
    assert line.kind == LINE
    assert line.length == pytest.approx(40)


def test_grid_line_merges_through_crossings():
    chains = build_chains(grid(3, 10.0, 4, overhang=1.0), TOL, MAX_ANGLE)
    segs = grid(3, 10.0, 4, overhang=1.0)
    for chain in chains:
        (line,) = compact_chain(segs, chain, TOL)
        assert line.length == pytest.approx(12)


def test_drift_beyond_tolerance_not_merged():
    # Polyline on a circle of radius 1000: every joint is almost straight
    # (0.06 deg) but the sagitta over 10 units is 0.0125, beyond tolerance.
    r = 1000.0
    pts = [(r * math.sin(i / r), r - r * math.cos(i / r)) for i in range(11)]
    segs = [line_segment(a, b) for a, b in zip(pts, pts[1:])]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    out = compact_chain(segs, chain, TOL)
    assert len(out) > 1
    for p in pts:
        assert min(_point_line_distance(p, s) for s in out) <= TOL


def test_arc_pieces_merge_and_circle_closes():
    segs = [
        arc_segment((0, 0), 1, i * 2 * math.pi / 5, 2 * math.pi / 5) for i in range(5)
    ]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    (arc,) = compact_chain(segs, chain, TOL)
    assert arc.kind == ARC
    assert arc.length == pytest.approx(2 * math.pi)


def test_arcs_with_different_radius_not_merged():
    a = arc_segment((0, 0), 1.0, 0, math.pi / 2)
    b = arc_segment((0, 1.0 - 1.01), 1.01, math.pi / 2, math.pi / 2)
    (chain,) = build_chains([a, b], TOL, MAX_ANGLE)
    assert len(compact_chain([a, b], chain, TOL)) == 2


def test_line_and_arc_never_merge():
    segs = [line_segment((-1, 0), (1, 0)), arc_segment((0, 0), 1, 0, math.pi)]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    assert len(compact_chain(segs, chain, TOL)) == 2


def test_rectangle_keeps_four_corners():
    segs = rectangle_edges(0, 0, 10, 6)
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    out = compact_chain(segs, chain, TOL)
    assert len(out) == 4
    assert out[-1].end == pytest.approx(out[0].start)


def test_closed_chain_merges_across_seam():
    # Square whose first and last segments are collinear halves of one side.
    pts = [(5, 0), (10, 0), (10, 10), (0, 10), (0, 0), (5, 0)]
    segs = [line_segment(a, b) for a, b in zip(pts, pts[1:])]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    assert len(compact_chain(segs, chain, TOL)) == 4


def test_merged_line_keeps_longest_source():
    segs = [
        line_segment((0, 0), (1, 0), source=4),
        line_segment((1, 0), (5, 0), source=9),
    ]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    (line,) = compact_chain(segs, chain, TOL)
    assert line.source == 9


def test_reversed_free_segment_keeps_ref_and_swaps_tangents():
    s = Segment(FREE, (0, 0), (1, 1), (1, 0), (0, -1), 2.0, source=3, ref=5)
    r = reversed_segment(s)
    assert (r.start, r.end, r.t_start, r.t_end) == ((1, 1), (0, 0), (0, -1), (1, 0))
    assert (r.source, r.ref) == (3, 5)


def test_line_tangent_to_circle_at_seam_keeps_circle_closed():
    line = line_segment((-2, 1), (0, 1))
    circle = arc_segment((0, 0), 1, math.pi / 2, -2 * math.pi)  # CW from top.
    chains = build_chains([line, circle], TOL, MAX_ANGLE)
    assert sorted((c.closed, tuple(c.items)) for c in chains) == [
        (False, ((0, False),)),
        (True, ((1, False),)),
    ]


def test_short_near_collinear_duplicate_found():
    a = line_segment((0, 0), (0.02, 0))
    b = line_segment((0, 0), (0.02, 0.0009))
    _, n = remove_overlaps([a, b], TOL)
    assert n == 1


def test_overlap_scales_on_one_support_line():
    d = (math.cos(0.005), math.sin(0.005))
    segs = [
        line_segment((d[0] * i, d[1] * i), (d[0] * (i + 1), d[1] * (i + 1)))
        for i in range(3000)
    ]
    start = time.perf_counter()
    _, n = remove_overlaps(segs, TOL)
    assert time.perf_counter() - start < 2.0
    assert n == 0


def test_compact_scales_on_long_collinear_chain():
    segs = [line_segment((i, 0), (i + 1, 0)) for i in range(4000)]
    (chain,) = build_chains(segs, TOL, MAX_ANGLE)
    start = time.perf_counter()
    (line,) = compact_chain(segs, chain, TOL)
    assert time.perf_counter() - start < 1.0
    assert line.length == pytest.approx(4000)


def test_backtracking_lines_not_merged():
    segs = [line_segment((0, 0), (2, 0)), line_segment((2, 0), (1, 0))]
    chain = Chain([(0, False), (1, False)], False)
    assert len(compact_chain(segs, chain, TOL)) == 2


def square(x0, y0, size, ccw=True):
    pts = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    if not ccw:
        pts.reverse()
    return [line_segment(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]


def loops(chains):
    return sorted(sorted(i for i, _ in c.items) for c in chains)


def test_split_corner_touch_gives_two_loops():
    segments = square(-1, -1, 1) + square(0, 0, 1)
    chains = build_chains(segments, TOL, math.pi, split_touches=True)
    assert all(c.closed for c in chains)
    assert loops(chains) == [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_split_holes_touching_gives_three_loops():
    segments = (
        square(-5, -5, 10)
        + square(-1, -1, 1, ccw=False)
        + square(0, 0, 1, ccw=False)
    )
    chains = build_chains(segments, TOL, math.pi, split_touches=True)
    assert all(c.closed for c in chains)
    assert loops(chains) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]


def test_split_skew_corner_touch():
    c, s = math.cos(0.5), math.sin(0.5)

    def rot(p):
        return (c * p[0] - s * p[1], s * p[0] + c * p[1])

    b = [line_segment(rot(g.start), rot(g.end)) for g in square(0, 0, 1)]
    chains = build_chains(square(-1, -1, 1) + b, TOL, math.pi, split_touches=True)
    assert len(chains) == 2 and all(ch.closed for ch in chains)


def test_split_off_keeps_todays_result():
    segments = square(-1, -1, 1) + square(0, 0, 1)
    assert build_chains(segments, TOL, MAX_ANGLE) == build_chains(
        segments, TOL, MAX_ANGLE, split_touches=False
    )
    assert len(build_chains(segments, TOL, math.pi)) == 1

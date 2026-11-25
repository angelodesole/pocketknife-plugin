"""Tests for pocketknife.curvegraph."""

import math
import random
import time

import pytest

from pocketknife.curvegraph import (
    arc_segment,
    drop_slivers,
    fuse_endpoints,
    line_segment,
    remove_overlaps,
)

TOL = 0.001


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

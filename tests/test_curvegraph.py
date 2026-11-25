"""Tests for pocketknife.curvegraph."""

import math

import pytest

from pocketknife.curvegraph import (
    arc_segment,
    drop_slivers,
    fuse_endpoints,
    line_segment,
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

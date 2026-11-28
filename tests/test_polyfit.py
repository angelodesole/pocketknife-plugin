"""Tests for pocketknife.polyfit."""

import math

import pytest

from pocketknife.polyfit import (
    dedupe,
    find_corners,
    partition,
    turning_angles,
)


def polygon(n, r=1.0, start=0.0, center=(0.0, 0.0)):
    return [
        (
            center[0] + r * math.cos(start + 2 * math.pi * k / n),
            center[1] + r * math.sin(start + 2 * math.pi * k / n),
            0.0,
        )
        for k in range(n)
    ]


def turtle(turns_deg, step=1.0, start=(0.0, 0.0)):
    """Open polyline: one edge, then for each turn rotate and add an edge."""
    x, y, h = start[0], start[1], 0.0
    pts = [(x, y, 0.0)]
    x, y = x + step, y
    pts.append((x, y, 0.0))
    for t in turns_deg:
        h += math.radians(t)
        x, y = x + step * math.cos(h), y + step * math.sin(h)
        pts.append((x, y, 0.0))
    return pts


def test_dedupe_removes_repeats_and_closing_point():
    pts = [(0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)]
    assert dedupe(pts, True, 1e-9) == [(0, 0, 0), (1, 0, 0), (1, 1, 0)]


def test_turning_angles_square():
    sq = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    assert turning_angles(sq, True) == pytest.approx([math.pi / 2] * 4)


def test_turning_angles_open_ends_zero():
    angles = turning_angles([(0, 0, 0), (1, 0, 0), (1, 1, 0)], False)
    assert angles == pytest.approx([0, math.pi / 2, 0])


def test_regular_24gon_has_no_corners():
    assert find_corners(polygon(24), True, math.radians(45)) == []


def test_octagon_all_corners_at_45():
    assert find_corners(polygon(8), True, math.radians(45)) == list(range(8))


def test_true_20_degree_corner_between_coarse_arcs():
    pts = turtle([15] * 5 + [35] + [15] * 5)
    corners = find_corners(pts, False, math.radians(45))
    assert corners == [0, 6, len(pts) - 1]


def test_tangent_join_line_arc_is_not_corner():
    pts = turtle([0, 0, 7.5] + [15] * 5)
    assert find_corners(pts, False, math.radians(45)) == [0, len(pts) - 1]


TOL = 0.001
CORNER = math.radians(45)


def rounded_rectangle(w=10.0, h=6.0, r=1.0, line_edges=3, arc_facets=6):
    """Closed ring: 4 lines and 4 quarter arcs, tangent joins."""
    centers = [(w - r, r), (w - r, h - r), (r, h - r), (r, r)]
    starts = [-90.0, 0.0, 90.0, 180.0]
    line_ends = [
        ((r, 0.0), (w - r, 0.0)),
        ((w, r), (w, h - r)),
        ((w - r, h), (r, h)),
        ((0.0, h - r), (0.0, r)),
    ]
    pts = []
    for (a, b), c, s0 in zip(line_ends, centers, starts):
        for k in range(line_edges):
            f = k / line_edges
            pts.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), 0.0))
        for k in range(arc_facets):
            ang = math.radians(s0 + 90.0 * k / arc_facets)
            pts.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang), 0.0))
    return pts


def cubic_samples(count=200):
    ts = [-1.5 + 3.0 * k / (count - 1) for k in range(count)]
    return [(t, t**3 - t, 0.0) for t in ts]


def _partition(pts, closed):
    return partition(pts, closed, TOL, find_corners(pts, closed, CORNER))


def test_24gon_is_one_circle():
    (run,) = _partition(polygon(24, 2.0, 0.3, (5.0, -1.0)), True)
    assert run.kind == "circle"
    assert run.center == pytest.approx((5.0, -1.0, 0.0), abs=1e-6)
    assert run.radius == pytest.approx(2.0, abs=1e-6)


def test_12gon_is_one_circle():
    (run,) = _partition(polygon(12), True)
    assert run.kind == "circle"


def test_rounded_rectangle_four_lines_four_arcs():
    runs = _partition(rounded_rectangle(), True)
    kinds = [r.kind for r in runs]
    assert sorted(kinds) == ["arc"] * 4 + ["line"] * 4
    assert all(a != b for a, b in zip(kinds, kinds[1:] + kinds[:1]))
    for r in runs:
        if r.kind == "arc":
            assert r.radius == pytest.approx(1.0, abs=1e-6)


def test_runs_cover_every_edge_once():
    pts = rounded_rectangle()
    runs = _partition(pts, True)
    covered = sum((r.end - r.start) % len(pts) for r in runs)
    assert covered == len(pts)


def test_dense_free_cubic_has_no_primitives():
    runs = _partition(cubic_samples(), False)
    assert [r.kind for r in runs] == ["free"]


def test_irregular_facets_not_an_arc():
    angles, a = [], 0.0
    for k in range(16):
        angles.append(a)
        a += math.radians(20.0 if k % 2 else 26.0)
    pts = [(math.cos(t), math.sin(t), 0.0) for t in angles]
    runs = _partition(pts, False)
    assert "arc" not in [r.kind for r in runs]


def test_open_polyline_with_corner_two_lines():
    pts = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (3, 1, 0), (3, 2, 0), (3, 3, 0)]
    runs = _partition(pts, False)
    assert [(r.kind, r.start, r.end) for r in runs] == [("line", 0, 3), ("line", 3, 6)]

"""Tests for pocketknife.polyfit."""

import math

import pytest

from pocketknife.polyfit import dedupe, find_corners, turning_angles


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

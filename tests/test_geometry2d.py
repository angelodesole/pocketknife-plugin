"""Tests for pocketknife.geometry2d."""

import math

import pytest

from pocketknife.geometry2d import (
    PERIMETER,
    Rect2D,
    alignment_rotation,
    convex_hull,
    group_loops_into_regions,
    min_bounding_rect,
    point_in_polygon,
    polylabel,
    signed_distance,
)


def _rotated_rect(w, h, angle, cx=0.0, cy=0.0):
    ca, sa = math.cos(angle), math.sin(angle)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in corners]


def test_convex_hull_drops_interior_points():
    pts = [(0, 0), (2, 0), (2, 2), (0, 2), (1, 1), (0.5, 1.5)]
    assert sorted(convex_hull(pts)) == [(0, 0), (0, 2), (2, 0), (2, 2)]


def test_min_rect_recovers_rotated_rectangle():
    pts = _rotated_rect(10, 4, math.radians(30), 5, -3) + [(5, -3)]
    rect = min_bounding_rect(pts)
    assert {round(rect.width, 6), round(rect.height, 6)} == {10.0, 4.0}
    assert rect.center == pytest.approx((5, -3))


def test_min_rect_perimeter_metric():
    rect = min_bounding_rect(_rotated_rect(6, 2, 0.4), metric=PERIMETER)
    assert rect.width + rect.height == pytest.approx(8.0)


def test_min_rect_degenerate_inputs():
    assert min_bounding_rect([(1, 1)]).width == 0.0
    rect = min_bounding_rect([(0, 0), (3, 4)])
    assert max(rect.width, rect.height) == pytest.approx(5.0)
    with pytest.raises(ValueError):
        min_bounding_rect([])


@pytest.mark.parametrize("angle_deg", [0, 20, 75, 90, 135, -60])
def test_alignment_rotation_puts_long_side_on_axis(angle_deg):
    rect = Rect2D((0, 0), math.radians(angle_deg), 10.0, 2.0)
    rot = alignment_rotation(rect, "X")
    assert -math.pi / 2 < rot <= math.pi / 2
    final = math.radians(angle_deg) + rot
    assert math.sin(final) == pytest.approx(0.0, abs=1e-9)
    rot_y = alignment_rotation(rect, "Y")
    assert math.cos(math.radians(angle_deg) + rot_y) == pytest.approx(0.0, abs=1e-9)


def test_polylabel_is_inside_concave_shape():
    # C shape: the centroid falls in the empty notch.
    c_shape = [(0, 0), (10, 0), (10, 2), (2, 2), (2, 8), (10, 8), (10, 10), (0, 10)]
    point = polylabel([c_shape])
    assert point_in_polygon(point, c_shape)
    assert signed_distance(point, [c_shape]) > 0.9


def test_polylabel_avoids_hole():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole = [(3, 3), (7, 3), (7, 7), (3, 7)]
    point = polylabel([outer, hole])
    assert not point_in_polygon(point, hole)
    # Best spot is on a diagonal, near a corner: d = 3*sqrt(2) / (1 + sqrt(2)).
    expected = 3 * math.sqrt(2) / (1 + math.sqrt(2))
    assert signed_distance(point, [outer, hole]) == pytest.approx(expected, abs=0.02)


def test_group_loops_into_regions():
    big = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole = [(2, 2), (8, 2), (8, 8), (2, 8)]
    island = [(4, 4), (6, 4), (6, 6), (4, 6)]
    separate = [(20, 0), (21, 0), (21, 1), (20, 1)]
    regions = group_loops_into_regions([island, separate, hole, big])
    assert len(regions) == 3
    assert regions[0] == [big, hole]
    assert regions[1] == [island]
    assert regions[2] == [separate]

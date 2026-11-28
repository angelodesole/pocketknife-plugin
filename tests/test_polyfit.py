"""Tests for pocketknife.polyfit."""

import math
import time

import pytest

from pocketknife.polyfit import (
    bspline_point,
    dedupe,
    find_corners,
    fit_free,
    fit_with,
    max_deviation,
    partition,
    rebuild,
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


def test_fit_free_cubic_few_points():
    pts = cubic_samples()
    kind, (degree, ctrl, knots) = fit_free(pts, TOL, None, None)
    assert kind == "nurbs" and degree == 3
    assert len(ctrl) <= 8
    assert max_deviation(pts, degree, ctrl, knots) <= TOL
    assert ctrl[0] == pts[0] and ctrl[-1] == pts[-1]
    assert len(knots) == len(ctrl) + degree + 1


def test_fit_is_minimal():
    pts = cubic_samples()
    _, (degree, ctrl, knots) = fit_free(pts, TOL, None, None)
    fewer = fit_with(pts, len(ctrl) - 1, None, None)
    assert fewer is None or max_deviation(pts, *fewer) > TOL


def test_end_tangents_respected():
    pts = cubic_samples()
    k = 1.0 / math.hypot(1.0, 5.75)
    tangent = (k, 5.75 * k, 0.0)  # Direction of (t, t^3 - t) at t = -1.5.
    _, (degree, ctrl, knots) = fit_free(pts, TOL, tangent, None)
    d = (ctrl[1][0] - ctrl[0][0], ctrl[1][1] - ctrl[0][1], ctrl[1][2] - ctrl[0][2])
    cross = d[0] * tangent[1] - d[1] * tangent[0]
    assert abs(cross) < 1e-9 and d[0] * tangent[0] + d[1] * tangent[1] > 0


def test_bspline_point_ends():
    pts = cubic_samples()
    _, (degree, ctrl, knots) = fit_free(pts, TOL, None, None)
    assert bspline_point(degree, ctrl, knots, 0.0) == pytest.approx(pts[0])
    assert bspline_point(degree, ctrl, knots, 1.0) == pytest.approx(pts[-1])


def test_three_points_quadratic():
    pts = [(0, 0, 0), (1, 1, 0), (2, 0, 0)]
    kind, (degree, ctrl, knots) = fit_free(pts, TOL, None, None)
    assert kind == "nurbs" and degree == 2
    assert max_deviation(pts, degree, ctrl, knots) <= TOL


def test_two_points_line():
    kind, (degree, ctrl, knots) = fit_free([(0, 0, 0), (1, 2, 3)], TOL, None, None)
    assert kind == "nurbs" and degree == 1 and len(ctrl) == 2


def test_large_run_speed():
    pts = [
        (t, math.sin(3 * t) + 0.2 * t * t, 0.0)
        for t in [k * 6.0 / 499 for k in range(500)]
    ]
    start = time.perf_counter()
    kind, data = fit_free(pts, TOL, None, None)
    assert time.perf_counter() - start < 2.0
    assert kind == "nurbs"
    assert max_deviation(pts, *data) <= TOL


def _circumcircle(a, b, c):
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    cx, cy = c[0], c[1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = (
        (ax**2 + ay**2) * (by - cy)
        + (bx**2 + by**2) * (cy - ay)
        + (cx**2 + cy**2) * (ay - by)
    ) / d
    uy = (
        (ax**2 + ay**2) * (cx - bx)
        + (bx**2 + by**2) * (ax - cx)
        + (cx**2 + cy**2) * (bx - ax)
    ) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def sample_piece(piece, count=400):
    kind, data = piece
    if kind == "line":
        a, b = data
        return [
            tuple(a[i] + (b[i] - a[i]) * k / count for i in range(3))
            for k in range(count + 1)
        ]
    if kind == "polyline":
        return list(data[0])
    if kind == "nurbs":
        degree, ctrl, knots = data
        return [bspline_point(degree, ctrl, knots, k / count) for k in range(count + 1)]
    if kind == "circle":
        center, normal, radius, start = data
        a0 = math.atan2(start[1] - center[1], start[0] - center[0])
        return [
            (
                center[0] + radius * math.cos(a0 + 2 * math.pi * k / count),
                center[1] + radius * math.sin(a0 + 2 * math.pi * k / count),
                0.0,
            )
            for k in range(count + 1)
        ]
    a, m, b = data  # planar XY arcs in these tests
    (ux, uy), r = _circumcircle(a, m, b)
    a0 = math.atan2(a[1] - uy, a[0] - ux)
    am = math.atan2(m[1] - uy, m[0] - ux)
    a1 = math.atan2(b[1] - uy, b[0] - ux)
    sweep = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    return [
        (
            ux + r * math.cos(a0 + sweep * k / count),
            uy + r * math.sin(a0 + sweep * k / count),
            0.0,
        )
        for k in range(count + 1)
    ]


def _seg_dist(q, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ll = sum(c * c for c in ab)
    t = 0.0 if ll == 0 else sum((q[i] - a[i]) * ab[i] for i in range(3)) / ll
    t = max(0.0, min(1.0, t))
    return math.dist(q, [a[i] + t * ab[i] for i in range(3)])


def assert_within(points, pieces, tol=TOL):
    polylines = [sample_piece(piece, 800) for piece in pieces]
    for q in points:
        d = min(
            _seg_dist(q, a, b) for line in polylines for a, b in zip(line, line[1:])
        )
        assert d <= tol * 1.01, (q, d)


def _tangent_at_start(piece):
    s = sample_piece(piece, 2000)
    return math.atan2(s[1][1] - s[0][1], s[1][0] - s[0][0])


def _tangent_at_end(piece):
    s = sample_piece(piece, 2000)
    return math.atan2(s[-1][1] - s[-2][1], s[-1][0] - s[-2][0])


def _angle_gap(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def test_rebuild_24gon_from_arbitrary_seam():
    pts = polygon(24, 3.0, 0.1)
    pts = pts[7:] + pts[:7]
    pieces = rebuild(pts, True, TOL, CORNER)
    assert [p[0] for p in pieces] == ["circle"]
    assert_within(pts, pieces)


def test_rebuild_rounded_rectangle():
    pts = rounded_rectangle()
    pieces = rebuild(pts, True, TOL, CORNER)
    assert sorted(p[0] for p in pieces) == ["arc"] * 4 + ["line"] * 4
    assert_within(pts, pieces)
    for a, b in zip(pieces, pieces[1:] + pieces[:1]):
        gap = _angle_gap(_tangent_at_end(a), _tangent_at_start(b))
        assert gap < math.radians(0.5)


def test_rebuild_free_cubic_with_inflection():
    pts = cubic_samples()
    pieces = rebuild(pts, False, TOL, CORNER)
    assert [p[0] for p in pieces] == ["nurbs"]
    assert_within(pts, pieces)


def test_rebuild_square_keeps_corners():
    pts = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
    pieces = rebuild(pts, True, TOL, CORNER)
    assert [p[0] for p in pieces] == ["line"] * 4


def test_rebuild_line_then_free():
    pts = [(-3.0 + k * 0.75, 0.0, 0.0) for k in range(4)]
    pts += [(x, x**3, 0.0) for x in [k * 1.5 / 120 for k in range(121)]]
    pieces = rebuild(pts, False, TOL, CORNER)
    assert [p[0] for p in pieces] == ["line", "nurbs"]
    assert_within(pts, pieces)
    gap = _angle_gap(_tangent_at_end(pieces[0]), _tangent_at_start(pieces[1]))
    assert gap < math.radians(0.5)


def test_rebuild_pieces_share_end_vertices():
    pieces = rebuild(rounded_rectangle(), True, TOL, CORNER)
    for a, b in zip(pieces, pieces[1:] + pieces[:1]):
        assert sample_piece(a)[-1] == pytest.approx(sample_piece(b)[0], abs=1e-9)


# Regression tests from the final review --------------------------------------


def _corner_angle_at(pieces, closed=True):
    """Angle between the end tangent of the last piece and the first start."""
    return _angle_gap(_tangent_at_end(pieces[-1]), _tangent_at_start(pieces[0]))


def test_single_corner_ring_keeps_its_corner():
    import random

    rng = random.Random(3)
    ts = sorted(rng.uniform(0.05, 2 * math.pi - 0.05) for _ in range(40))
    pts = [(0.0, 0.0, 0.0)] + [
        (4 * math.sin(t / 2), 1.5 * math.sin(t), 0.0) for t in ts
    ]
    pieces = rebuild(pts, True, TOL, CORNER)
    assert_within(pts, pieces)
    assert _corner_angle_at(pieces) > math.radians(60)


def _irregular_arc(center, r, degs):
    return [
        (
            center[0] + r * math.cos(math.radians(d)),
            center[1] + r * math.sin(math.radians(d)),
            0.0,
        )
        for d in degs
    ]


def test_free_fit_does_not_loop_between_vertices():
    a = _irregular_arc((0, 0), 2, [270, 279, 300, 322, 336, 351, 360])
    b = [(2.0, 8.0, 0.0)]
    c = _irregular_arc((0, 8), 2, [0, 13, 27, 48, 71, 90])
    pts = a + b + c[1:]
    pieces = rebuild(pts, False, 0.005, CORNER)
    assert_within(pts, pieces, 0.005)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for piece in pieces:
        for q in sample_piece(piece, 400):
            assert min(xs) - 1 <= q[0] <= max(xs) + 1
            assert min(ys) - 1 <= q[1] <= max(ys) + 1


def test_seam_inside_arc_still_four_lines_four_arcs():
    pts = rounded_rectangle(w=10.0, h=6.0, r=2.0, line_edges=1, arc_facets=6)
    pts = pts[1:] + pts[:1]  # Start at the first vertex inside an arc.
    pieces = rebuild(pts, True, TOL, CORNER)
    assert sorted(p[0] for p in pieces) == ["arc"] * 4 + ["line"] * 4


def test_dense_inflection_has_no_line():
    pts = [(t, t**3 - t, 0.0) for t in [-1.5 + 3.0 * k / 500 for k in range(501)]]
    runs = _partition(pts, False)
    assert [r.kind for r in runs] == ["free"]


def test_dense_ellipse_has_no_arcs():
    pts = [
        (10 * math.cos(2 * math.pi * k / 200), 9 * math.sin(2 * math.pi * k / 200), 0.0)
        for k in range(200)
    ]
    runs = _partition(pts, True)
    assert "arc" not in [r.kind for r in runs]


def test_three_vertex_free_run_follows_neighbour_tangents():
    pts = [(0.0, 0.0, 0.0), (0.5, -0.5, 0.0), (1.0, 0.0, 0.0)]
    kind, (degree, ctrl, knots) = fit_free(pts, 0.01, (0.0, -1.0, 0.0), (0.0, 1.0, 0.0))
    assert kind == "nurbs" and degree == 3
    assert max_deviation(pts, degree, ctrl, knots) <= 0.01
    start = (ctrl[1][0] - ctrl[0][0], ctrl[1][1] - ctrl[0][1])
    end = (ctrl[-1][0] - ctrl[-2][0], ctrl[-1][1] - ctrl[-2][1])
    assert abs(start[0]) < 1e-9 and start[1] < 0
    assert abs(end[0]) < 1e-9 and end[1] > 0


def test_clockwise_ring_gives_clockwise_circle():
    pts = list(reversed(polygon(24)))
    ((kind, (center, normal, radius, start)),) = rebuild(pts, True, TOL, CORNER)
    assert kind == "circle" and normal[2] < 0


def test_forced_corner_is_kept():
    pts = turtle([0, 0, 0, 3, 0, 0, 0], step=1.0)  # 3 degree kink at vertex 4
    pieces = rebuild(pts, False, TOL, CORNER, forced_corners=[4])
    assert [p[0] for p in pieces] == ["line", "line"]

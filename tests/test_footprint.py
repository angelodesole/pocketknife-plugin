from pocketknife.footprint import keep_loops, loop_depths, nest_loops


def sq(x0, y0, size):
    return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]


def test_nest_disjoint():
    polys = [sq(0, 0, 1), sq(5, 0, 1)]
    assert nest_loops(polys, [1, 1]) == [-1, -1]


def test_nest_three_levels():
    polys = [sq(2, 2, 1), sq(0, 0, 10), sq(1, 1, 5)]
    parents = nest_loops(polys, [1, 100, 25])
    assert parents == [2, -1, 1]
    assert loop_depths(parents) == [2, 0, 1]


def test_nest_siblings():
    polys = [sq(0, 0, 10), sq(1, 1, 2), sq(5, 5, 2)]
    assert nest_loops(polys, [100, 4, 4]) == [-1, 0, 0]


def test_nest_corner_touch_siblings():
    polys = [sq(-1, -1, 1), sq(0, 0, 1)]
    assert nest_loops(polys, [1, 1]) == [-1, -1]


def test_keep_small_island_dropped():
    assert keep_loops([-1, -1], [100, 0.5], 1.0) == [0]


def test_keep_small_hole_takes_inner_island():
    # island 0 > hole 1 (small) > island 2
    assert keep_loops([-1, 0, 1], [100, 0.8, 0.1], 1.0) == [0]


def test_keep_big_island_small_hole():
    assert keep_loops([-1, 0], [100, 0.5], 1.0) == [0]


def test_keep_zero_and_exact():
    assert keep_loops([-1, 0], [100, 0.5], 0.0) == [0, 1]
    assert keep_loops([-1], [1.0], 1.0) == [0]


def test_nest_scales():
    import time

    polys, areas = [], []
    for i in range(60):
        for j in range(60):
            polys.append(sq(i * 3, j * 3, 2))
            areas.append(4.0)
    t = time.perf_counter()
    assert nest_loops(polys, areas) == [-1] * 3600
    assert time.perf_counter() - t < 2.0

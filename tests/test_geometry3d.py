"""Tests for pocketknife.geometry3d."""

import math
import random

import pytest

from pocketknife.geometry3d import CancelledError, min_bounding_box


def _rotate(p, ax, ay, az):
    x, y, z = p
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
    return (x, y, z)


def test_recovers_rotated_box():
    corners = [(x, y, z) for x in (-5, 5) for y in (-2, 2) for z in (-1, 1)]
    rng = random.Random(1)
    inner = [
        (rng.uniform(-5, 5), rng.uniform(-2, 2), rng.uniform(-1, 1)) for _ in range(50)
    ]
    pts = [_rotate(p, 0.3, 0.7, 1.1) for p in corners + inner]
    box = min_bounding_box(pts)
    assert box.volume == pytest.approx(80.0, rel=1e-3)
    assert sorted(box.sizes) == pytest.approx([2.0, 4.0, 10.0], rel=1e-3)


def test_flat_input_has_zero_volume():
    pts = [(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)]
    box = min_bounding_box(pts, accuracy="Fast")
    assert box.volume == pytest.approx(0.0, abs=1e-9)


def test_empty_input_raises():
    with pytest.raises(ValueError):
        min_bounding_box([])


def test_progress_reports_and_cancels():
    pts = [(x, y, z) for x in (0, 1) for y in (0, 2) for z in (0, 3)]
    seen = []
    min_bounding_box(pts, "Fast", progress=lambda f: seen.append(f) or True)
    assert seen and seen[-1] == 1.0
    with pytest.raises(CancelledError):
        min_bounding_box(pts, "Fast", progress=lambda f: False)

"""Tests for pocketknife.intervals."""

from pocketknife.intervals import BOUNDARY, Piece, split_domain


def test_one_crossing_gives_two_pieces():
    assert split_domain((0, 10), [4], [], False, 1e-9) == [
        Piece(0, 4, ""),
        Piece(4, 10, ""),
    ]


def test_overlap_in_the_middle():
    assert split_domain((0, 10), [], [(3, 6)], False, 1e-9) == [
        Piece(0, 3, ""),
        Piece(3, 6, BOUNDARY),
        Piece(6, 10, ""),
    ]


def test_overlap_at_the_end():
    assert split_domain((0, 10), [2], [(7, 10)], False, 1e-9) == [
        Piece(0, 2, ""),
        Piece(2, 7, ""),
        Piece(7, 10, BOUNDARY),
    ]


def test_split_at_domain_end_adds_no_piece():
    assert split_domain((0, 10), [0, 10, 5], [], False, 1e-6) == [
        Piece(0, 5, ""),
        Piece(5, 10, ""),
    ]


def test_duplicate_splits_fuse():
    assert split_domain((0, 10), [4, 4 + 1e-9, 4], [], False, 1e-6) == [
        Piece(0, 4, ""),
        Piece(4, 10, ""),
    ]


def test_whole_domain_overlap_is_boundary():
    assert split_domain((0, 10), [], [(0, 10)], True, 1e-6) == [Piece(0, 10, BOUNDARY)]


def test_closed_curve_joins_across_seam():
    assert split_domain((0, 10), [2, 7], [], True, 1e-9) == [
        Piece(2, 7, ""),
        Piece(7, 2, ""),
    ]


def test_closed_curve_without_splits():
    assert split_domain((0, 10), [], [], True, 1e-9) == [Piece(0, 10, "")]


def test_overlap_wrapping_the_seam():
    assert split_domain((0, 10), [5], [(8, 1)], True, 1e-9) == [
        Piece(1, 5, ""),
        Piece(5, 8, ""),
        Piece(8, 1, BOUNDARY),
    ]

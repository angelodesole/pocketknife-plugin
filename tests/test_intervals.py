"""Tests for pocketknife.intervals."""

from pocketknife.intervals import (
    BOUNDARY,
    DROP,
    INSIDE,
    OUTSIDE,
    Piece,
    covers_domain,
    even_odd,
    keep_pieces,
    merge_same_state,
    split_domain,
)


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


def test_even_odd():
    assert [even_odd(c) for c in range(4)] == [OUTSIDE, INSIDE, OUTSIDE, INSIDE]


def test_touch_merges_back():
    pieces = [Piece(0, 4, INSIDE), Piece(4, 10, INSIDE)]
    merged = merge_same_state(pieces, False, (0, 10))
    assert merged == [Piece(0, 10, INSIDE)]
    assert covers_domain(merged, (0, 10))


def test_boundary_never_merged_nor_kept():
    pieces = [Piece(0, 3, INSIDE), Piece(3, 6, BOUNDARY), Piece(6, 10, INSIDE)]
    merged = merge_same_state(pieces, False, (0, 10))
    assert len(merged) == 3
    assert not covers_domain(merged, (0, 10))
    assert keep_pieces(merged, True) == [Piece(0, 3, INSIDE), Piece(6, 10, INSIDE)]
    assert keep_pieces(merged, False) == []


def test_closed_merge_across_seam():
    pieces = [Piece(2, 7, OUTSIDE), Piece(7, 9, INSIDE), Piece(9, 2, OUTSIDE)]
    assert merge_same_state(pieces, True, (0, 10)) == [
        Piece(7, 9, INSIDE),
        Piece(9, 7, OUTSIDE),
    ]


def test_closed_all_same_state_is_whole_domain():
    pieces = [Piece(2, 7, INSIDE), Piece(7, 2, INSIDE)]
    merged = merge_same_state(pieces, True, (0, 10))
    assert merged == [Piece(0, 10, INSIDE)]
    assert covers_domain(merged, (0, 10))


def test_drop_pieces_block_merge():
    pieces = [Piece(0, 4, INSIDE), Piece(4, 4.0001, DROP), Piece(4.0001, 10, INSIDE)]
    assert len(merge_same_state(pieces, False, (0, 10))) == 3


def test_whole_boundary_curve_not_kept():
    merged = merge_same_state([Piece(0, 10, BOUNDARY)], True, (0, 10))
    assert keep_pieces(merged, True) == []
    assert keep_pieces(merged, False) == []

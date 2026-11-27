"""Pure-Python parameter interval logic for clipping curves (no Rhino).

A curve domain is cut at split parameters (mask crossings) and at the ends of
overlap intervals (stretches lying on a mask boundary). The resulting pieces
are classified, merged when neighbours share a state, and filtered.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

INSIDE = "inside"
OUTSIDE = "outside"
BOUNDARY = "boundary"
DROP = "drop"


class Piece(NamedTuple):
    """A parameter interval of a curve.

    Attributes:
        t0: Start parameter.
        t1: End parameter. On a closed curve a piece crossing the seam has
            ``t0 > t1``.
        state: ``INSIDE``, ``OUTSIDE``, ``BOUNDARY``, ``DROP`` or ``""``
            (not classified yet).
    """

    t0: float
    t1: float
    state: str


def _in_interval(t: float, lo: float, hi: float) -> bool:
    if lo <= hi:
        return lo <= t <= hi
    return t >= lo or t <= hi


def piece_mid(piece: Piece, domain: tuple[float, float]) -> float:
    """Middle parameter of a piece, across the seam if needed.

    Args:
        piece: The piece.
        domain: Curve domain ``(min, max)``.

    Returns:
        The middle parameter, inside the domain.
    """
    lo, hi = domain
    if piece.t0 <= piece.t1:
        return 0.5 * (piece.t0 + piece.t1)
    span = (hi - piece.t0) + (piece.t1 - lo)
    mid = piece.t0 + 0.5 * span
    return mid - (hi - lo) if mid > hi else mid


def split_domain(
    domain: tuple[float, float],
    splits: Sequence[float],
    overlaps: Sequence[tuple[float, float]],
    closed: bool,
    param_tol: float,
) -> list[Piece]:
    """Cuts a curve domain into pieces.

    Args:
        domain: Curve domain ``(min, max)``.
        splits: Parameters where the curve crosses or touches a mask.
        overlaps: Parameter intervals lying on a mask boundary; on a closed
            curve an interval may wrap the seam (``lo > hi``).
        closed: True for a closed curve.
        param_tol: Parameters closer than this are the same cut.

    Returns:
        Pieces in domain order, tagged ``BOUNDARY`` when inside an overlap and
        ``""`` otherwise. On a closed curve the piece across the seam is last.
    """
    lo, hi = domain
    cuts = []
    for t in list(splits) + [t for interval in overlaps for t in interval]:
        t = min(max(t, lo), hi)
        if t - lo <= param_tol or hi - t <= param_tol:
            if not closed:
                continue
            t = lo
        cuts.append(t)
    cuts.sort()
    fused: list[float] = []
    for t in cuts:
        if not fused or t - fused[-1] > param_tol:
            fused.append(t)
    if closed:
        if len(fused) < 2:
            pieces = [Piece(lo, hi, "")]
        else:
            pieces = [Piece(a, b, "") for a, b in zip(fused, fused[1:])]
            last = Piece(fused[-1], fused[0], "")
            if fused[0] == lo:
                last = Piece(fused[-1], hi, "")
            pieces.append(last)
    else:
        stops = [lo] + fused + [hi]
        pieces = [Piece(a, b, "") for a, b in zip(stops, stops[1:])]
    out = []
    for piece in pieces:
        mid = piece_mid(piece, domain)
        on_boundary = any(_in_interval(mid, a, b) for a, b in overlaps)
        out.append(piece._replace(state=BOUNDARY if on_boundary else ""))
    return out


def even_odd(count: int) -> str:
    """Even-odd rule: inside when an odd number of mask loops contain a point.

    Args:
        count: Number of mask loops containing the point.

    Returns:
        ``INSIDE`` or ``OUTSIDE``.
    """
    return INSIDE if count % 2 else OUTSIDE


_MERGEABLE = (INSIDE, OUTSIDE)


def merge_same_state(
    pieces: list[Piece], closed: bool, domain: tuple[float, float]
) -> list[Piece]:
    """Merges neighbouring pieces that are both inside or both outside.

    A touch of the mask boundary thus leaves the curve in one piece.
    ``BOUNDARY`` and ``DROP`` pieces never merge.

    Args:
        pieces: Classified pieces in domain order (seam piece last).
        closed: True for a closed curve.
        domain: Curve domain ``(min, max)``.

    Returns:
        Merged pieces. A closed curve whose pieces all merge becomes one piece
        over the whole domain.
    """
    out: list[Piece] = []
    for piece in pieces:
        if out and out[-1].state == piece.state and piece.state in _MERGEABLE:
            out[-1] = out[-1]._replace(t1=piece.t1)
        else:
            out.append(piece)
    if closed and len(out) > 1:
        first, last = out[0], out[-1]
        if first.state == last.state and first.state in _MERGEABLE:
            out = out[1:-1] + [Piece(last.t0, first.t1, first.state)]
    if closed and len(out) == 1 and out[0].state in _MERGEABLE:
        out = [Piece(domain[0], domain[1], out[0].state)]
    return out


def keep_pieces(pieces: list[Piece], keep_inside: bool) -> list[Piece]:
    """Selects the pieces to keep.

    Args:
        pieces: Classified pieces.
        keep_inside: True to keep ``INSIDE`` pieces, False for ``OUTSIDE``.

    Returns:
        The kept pieces, in order.
    """
    wanted = INSIDE if keep_inside else OUTSIDE
    return [p for p in pieces if p.state == wanted]


def covers_domain(pieces: list[Piece], domain: tuple[float, float]) -> bool:
    """True if a single piece spans the whole domain (curve left whole).

    Args:
        pieces: Merged pieces.
        domain: Curve domain ``(min, max)``.

    Returns:
        Whether the curve stays in one piece.
    """
    return len(pieces) == 1 and pieces[0].t0 == domain[0] and pieces[0].t1 == domain[1]

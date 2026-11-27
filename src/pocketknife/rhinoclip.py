"""Rhino adapter for clipping curves with mask shapes (even-odd rule).

Only importable inside Rhino 8 (CPython 3.9 runtime). The interval logic is
in ``pocketknife.intervals``.
"""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from typing import NamedTuple

import Rhino.Geometry as rg
from Rhino.Geometry.Intersect import Intersection

from pocketknife.intervals import (
    BOUNDARY,
    DROP,
    Piece,
    covers_domain,
    even_odd,
    keep_pieces,
    merge_same_state,
    split_domain,
)


class MaskSet(NamedTuple):
    """Mask loops on one plane.

    Attributes:
        loops: Closed planar mask curves.
        boxes: 2D box ``(xmin, ymin, xmax, ymax)`` of each loop, in plane
            coordinates.
        plane: The mask plane, or None if there is no valid loop.
        ignored: Number of selected objects that are not usable masks.
        error: Empty when the mask set is usable, else the reason.
        used: Indices of the input geometries that gave at least one loop.
    """

    loops: list
    boxes: list
    plane: object
    ignored: int
    error: str
    used: list


class ClipResult(NamedTuple):
    """Result of ``clip_curves``.

    Attributes:
        pieces: Kept pieces.
        origins: Index of the input curve of each piece.
        untouched: Inputs kept whole; leave them in place.
        removed: Inputs replaced by their pieces or dropped whole.
        boundary: Number of stretches dropped because they lie on a mask
            boundary.
        failed: Inputs left as they are because Rhino could not project or
            trim them (also listed in ``untouched``).
    """

    pieces: list
    origins: list
    untouched: list
    removed: list
    boundary: int
    failed: list


def _box2d(curve: rg.Curve, to_plane: rg.Transform, tol: float) -> tuple:
    box = curve.GetBoundingBox(to_plane)
    return (box.Min.X - tol, box.Min.Y - tol, box.Max.X + tol, box.Max.Y + tol)


def _boxes_touch(a: tuple, b: tuple) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def mask_set(geometries: Sequence, tol: float, angle_tol: float) -> MaskSet:
    """Collects the mask loops of closed planar curves and hatches.

    Args:
        geometries: Selected mask geometry (curves, hatches).
        tol: Absolute tolerance.
        angle_tol: Angle tolerance in radians, for coplanarity.

    Returns:
        The mask set; ``error`` says why it is unusable, if it is.
    """
    loops, ignored, used = [], 0, []
    for index, geometry in enumerate(geometries):
        if isinstance(geometry, rg.Hatch):
            found = list(geometry.Get3dCurves(True)) + list(geometry.Get3dCurves(False))
        elif isinstance(geometry, rg.Curve):
            found = [geometry]
        else:
            ignored += 1
            continue
        usable = [c for c in found if c.IsClosed and c.IsPlanar(tol)]
        if not usable:
            ignored += 1
        else:
            used.append(index)
        loops += usable
    if not loops:
        return MaskSet([], [], None, ignored, "No closed planar mask shape.", used)
    ok, plane = loops[0].TryGetPlane(tol)
    if not ok:
        return MaskSet([], [], None, ignored, "No closed planar mask shape.", used)
    for loop in loops[1:]:
        ok, other = loop.TryGetPlane(tol)
        if (
            not ok
            or other.ZAxis.IsParallelTo(plane.ZAxis, angle_tol) == 0
            or abs(plane.DistanceTo(loop.PointAtStart)) > tol
        ):
            return MaskSet(
                [], [], None, ignored, "Mask shapes are not on one plane.", used
            )
    to_plane = rg.Transform.PlaneToPlane(plane, rg.Plane.WorldXY)
    boxes = [_box2d(loop, to_plane, 0.0) for loop in loops]
    return MaskSet(loops, boxes, plane, ignored, "", used)


def _in_plane(curve: rg.Curve, plane: rg.Plane, tol: float) -> bool:
    if not curve.IsPlanar(tol):
        return False
    domain = curve.Domain
    samples = [domain.ParameterAt(k / 8.0) for k in range(9)]
    return all(abs(plane.DistanceTo(curve.PointAt(t))) <= tol for t in samples)


class _Index:
    """Mask boxes sorted by xmin, for quick candidate lookup."""

    def __init__(self, boxes: list) -> None:
        self.order = sorted(range(len(boxes)), key=lambda i: boxes[i][0])
        self.xmins = [boxes[i][0] for i in self.order]
        self.boxes = boxes

    def candidates(self, box: tuple) -> list:
        end = bisect.bisect_right(self.xmins, box[2])
        return [i for i in self.order[:end] if _boxes_touch(self.boxes[i], box)]


def _state(probe: rg.Point3d, candidates: list, masks: MaskSet, to_plane, tol: float):
    """Even-odd state of a point, or None if it lies on a mask boundary."""
    local = rg.Point3d(probe)
    local.Transform(to_plane)
    count = 0
    for i in candidates:
        box = masks.boxes[i]
        if not (box[0] <= local.X <= box[2] and box[1] <= local.Y <= box[3]):
            continue
        result = masks.loops[i].Contains(probe, masks.plane, tol)
        if result == rg.PointContainment.Coincident:
            return None
        if result == rg.PointContainment.Inside:
            count += 1
    return even_odd(count)


def _classify(proj, piece: Piece, candidates, masks, to_plane, tol) -> str:
    domain = (proj.Domain.Min, proj.Domain.Max)
    t0, t1 = piece.t0, piece.t1
    if t0 <= t1:
        params = [t0 + f * (t1 - t0) for f in (0.5, 0.25, 0.75)]
    else:
        span = (domain[1] - t0) + (t1 - domain[0])
        params = []
        for f in (0.5, 0.25, 0.75):
            t = t0 + f * span
            params.append(t - (domain[1] - domain[0]) if t > domain[1] else t)
    first = _state(proj.PointAt(params[0]), candidates, masks, to_plane, tol)
    if first is not None:
        return first
    votes = [
        _state(proj.PointAt(t), candidates, masks, to_plane, tol) for t in params[1:]
    ]
    votes = [v for v in votes if v is not None]
    if len(votes) == 2 and votes[0] == votes[1]:
        return votes[0]
    return BOUNDARY


def _length(curve: rg.Curve, piece: Piece) -> float:
    if piece.t0 <= piece.t1:
        return curve.GetLength(rg.Interval(piece.t0, piece.t1))
    domain = curve.Domain
    return curve.GetLength(rg.Interval(piece.t0, domain.Max)) + curve.GetLength(
        rg.Interval(domain.Min, piece.t1)
    )


def clip_curves(
    curves: Sequence, masks: MaskSet, tol: float, keep_inside: bool
) -> ClipResult:
    """Clips curves with a mask set (even-odd), dropping on-boundary stretches.

    Args:
        curves: Curves to clip (``Rhino.Geometry.Curve``).
        masks: A usable mask set from ``mask_set``.
        tol: Absolute tolerance.
        keep_inside: True to keep the inside pieces, False the outside ones.

    Returns:
        The clipping result.
    """
    plane = masks.plane
    to_plane = rg.Transform.PlaneToPlane(plane, rg.Plane.WorldXY)
    flatten = rg.Transform.PlanarProjection(plane)
    index = _Index(masks.boxes)
    wanted = "inside" if keep_inside else "outside"
    result = ClipResult([], [], [], [], 0, [])
    boundary = 0
    for k, curve in enumerate(curves):
        if curve is None:
            continue
        if _in_plane(curve, plane, tol):
            work, proj = curve, curve
        else:
            work = curve.ToNurbsCurve()
            proj = work.DuplicateCurve() if work is not None else None
            if proj is None or not proj.Transform(flatten):
                result.untouched.append(k)
                result.failed.append(k)
                continue
        candidates = index.candidates(_box2d(proj, to_plane, tol))
        if proj.GetLength() <= tol:
            state = _state(proj.PointAtStart, candidates, masks, to_plane, tol)
            (result.untouched if state == wanted else result.removed).append(k)
            continue
        splits, overlaps = [], []
        for i in candidates:
            events = Intersection.CurveCurve(proj, masks.loops[i], tol, tol)
            if events is None:
                continue
            for event in events:
                if event.IsOverlap:
                    interval = event.OverlapA
                    if curve.IsClosed:
                        overlaps.append((interval.T0, interval.T1))
                    else:
                        overlaps.append((interval.Min, interval.Max))
                else:
                    splits.append(event.ParameterA)
        domain = (proj.Domain.Min, proj.Domain.Max)
        param_tol = tol * proj.Domain.Length / max(proj.GetLength(), tol)
        pieces = split_domain(domain, splits, overlaps, curve.IsClosed, param_tol)
        classified = []
        for piece in pieces:
            if _length(proj, piece) <= tol:
                classified.append(piece._replace(state=DROP))
            elif piece.state == BOUNDARY:
                classified.append(piece)
            else:
                state = _classify(proj, piece, candidates, masks, to_plane, tol)
                classified.append(piece._replace(state=state))
        merged = merge_same_state(classified, curve.IsClosed, domain)
        boundary += sum(1 for p in merged if p.state == BOUNDARY)
        if covers_domain(merged, domain):
            (result.untouched if merged[0].state == wanted else result.removed).append(
                k
            )
            continue
        trimmed = [work.Trim(p.t0, p.t1) for p in keep_pieces(merged, keep_inside)]
        if any(c is None or not c.IsValid for c in trimmed):
            # Never lose geometry: leave the curve as it is.
            result.untouched.append(k)
            result.failed.append(k)
            continue
        result.removed.append(k)
        result.pieces.extend(trimmed)
        result.origins.extend([k] * len(trimmed))
    return result._replace(boundary=boundary)

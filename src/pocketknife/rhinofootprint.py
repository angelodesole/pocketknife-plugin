"""Rhino side of pkFootprint: the outline of a union of objects on a plane.

The Make2D engine (``HiddenLineDrawing``) draws the objects in a parallel
view along the plane normal; the visible scene-silhouette segments are the
outline of their union. They are joined with the pkCleanCurves pipeline,
nested in pure Python (``pocketknife.footprint``) and filtered by area.

Only importable inside Rhino 8 (CPython 3.9 runtime).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import NamedTuple

import Rhino
import Rhino.Geometry as rg

from pocketknife.footprint import keep_loops, loop_depths, nest_loops
from pocketknife.rhinocurves import clean_curves

_MAX_BLOCK_DEPTH = 32


class FootprintResult(NamedTuple):
    """Result of ``footprint``.

    Attributes:
        closed: Closed outline curves kept (islands and holes).
        open: Curves that could not be closed.
        regions: Number of kept islands.
        holes: Number of kept holes.
        dropped: Number of closed loops removed by the area filter.
        error: Empty on success, otherwise a message; nothing else is set.
    """

    closed: list
    open: list
    regions: int
    holes: int
    dropped: int
    error: str


def _engine_geometry(geometry):
    """Geometry the hidden-line engine accepts, or None."""
    if isinstance(geometry, (rg.Brep, rg.Extrusion, rg.Mesh)):
        return geometry
    if isinstance(geometry, rg.SubD):
        return geometry.ToBrep(rg.SubDToBrepOptions.Default)
    return None


def _collect(obj, xform, depth, out) -> int:
    """Appends the engine items of one object; returns the number skipped."""
    if isinstance(obj, Rhino.DocObjects.InstanceObject):
        definition = obj.InstanceDefinition
        if definition is None or depth >= _MAX_BLOCK_DEPTH:
            return 1
        inner = xform * obj.InstanceXform
        skipped = 0
        for child in definition.GetObjects():
            skipped += _collect(child, inner, depth + 1, out)
        return skipped
    geometry = obj.Geometry if isinstance(obj, Rhino.DocObjects.RhinoObject) else obj
    geometry = _engine_geometry(geometry)
    if geometry is None:
        return 1
    out.append((geometry, xform))
    return 0


def collect_geometry(objects: Sequence) -> tuple[list, int]:
    """Collects the geometry of the objects for ``footprint``.

    Block instances are flattened recursively, multiplying their transforms.

    Args:
        objects: ``RhinoObject``s or bare ``GeometryBase`` (Grasshopper).

    Returns:
        A list of ``(geometry, Transform)`` and the number of objects (or
        block members) skipped as unsupported.
    """
    items: list = []
    skipped = 0
    for obj in objects:
        if obj is None:
            skipped += 1
            continue
        skipped += _collect(obj, rg.Transform.Identity, 0, items)
    return items, skipped


def _parallel_viewport(plane: rg.Plane, bbox: rg.BoundingBox):
    """Parallel viewport looking at the plane along its normal."""
    vp = Rhino.DocObjects.ViewportInfo()
    vp.ChangeToParallelProjection(True)
    distance = max(bbox.Diagonal.Length, 1.0) * 2.0
    vp.SetCameraLocation(bbox.Center + plane.ZAxis * distance)
    vp.SetCameraDirection(plane.ZAxis * -1.0)
    vp.SetCameraUp(plane.YAxis)
    vp.Extents(math.radians(20.0), bbox)
    return vp


def _silhouettes(items: list, plane: rg.Plane, tol: float):
    """Visible scene-silhouette segments on the plane.

    Returns:
        The segments, ``[]`` when the engine accepts no item, or None when
        the computation fails.
    """
    params = rg.HiddenLineDrawingParameters()
    params.AbsoluteTolerance = tol
    params.Flatten = True
    params.IncludeHiddenCurves = False
    params.IncludeTangentEdges = False
    params.IncludeTangentSeams = False
    bbox = rg.BoundingBox.Empty
    added = 0
    for geometry, xform in items:
        if params.AddGeometry(geometry, xform, None):
            added += 1
            bbox.Union(geometry.GetBoundingBox(xform))
    if not added:
        return []
    params.SetViewport(_parallel_viewport(plane, bbox))
    hld = rg.HiddenLineDrawing.Compute(params, True)
    if hld is None:
        return None
    try:
        ok, to_world = hld.WorldToHiddenLine.TryGetInverse()
        if not ok:
            return None
        flatten = rg.Transform.PlanarProjection(plane)
        visible = rg.HiddenLineDrawingSegment.Visibility.Visible
        segments = []
        for segment in hld.Segments:
            if segment.SegmentVisibility != visible:
                continue
            if not segment.IsSceneSilhouette:
                continue
            curve = segment.CurveGeometry.DuplicateCurve()
            curve.Transform(to_world)
            curve.Transform(flatten)
            segments.append(curve)
    finally:
        hld.Dispose()
    return segments


def _true_arc(curve, plane: rg.Plane, tol: float):
    """Returns an ``ArcCurve`` for a circular curve, else the curve itself.

    Faceted curves (mesh outlines) are kept as they are, however close to a
    circle their vertices lie.
    """
    if curve.Degree == 1 or curve.TryGetPolyline()[0]:
        return curve
    if curve.IsClosed:
        ok, circle = curve.TryGetCircle(tol)
        if ok:
            return rg.ArcCurve(circle)
        return curve
    ok, arc = curve.TryGetArc(plane, tol)
    if ok:
        return rg.ArcCurve(arc)
    return curve


def _polygon(curve, plane: rg.Plane, tol: float) -> list:
    """Vertices of a closed curve in plane coordinates, within ``tol``."""
    ok, polyline = curve.TryGetPolyline()
    if ok:
        points = list(polyline)
    else:
        approx = curve.ToPolyline(0, 0, 0, 0, 0, tol, 0, 0, True)
        points = list(approx.ToPolyline()) if approx is not None else []
    if len(points) > 1 and points[0].DistanceTo(points[-1]) <= tol:
        points.pop()
    polygon = []
    for point in points:
        _, u, v = plane.ClosestParameter(point)
        polygon.append((u, v))
    return polygon


def _area(curve, polygon: list) -> float:
    """Enclosed area of a closed planar curve (shoelace as a fallback)."""
    props = rg.AreaMassProperties.Compute(curve)
    if props is not None:
        return abs(props.Area)
    twice = 0.0
    for i, (x0, y0) in enumerate(polygon):
        x1, y1 = polygon[(i + 1) % len(polygon)]
        twice += x0 * y1 - x1 * y0
    return abs(twice) / 2.0


def footprint(
    items: list, plane: rg.Plane, tol: float, gap_tol: float, min_area: float
) -> FootprintResult:
    """Computes the outline of the union of the items on a plane.

    Args:
        items: ``(geometry, Transform)`` pairs from ``collect_geometry``.
        plane: Projection plane; objects are seen along its normal.
        tol: Model absolute tolerance.
        gap_tol: Distance within which outline ends are joined.
        min_area: Closed loops with a smaller area are dropped, with
            everything inside them; zero or less keeps everything.

    Returns:
        The footprint result.
    """
    if not items:
        return FootprintResult([], [], 0, 0, 0, "No supported objects.")
    segments = _silhouettes(items, plane, tol)
    if segments is None:
        return FootprintResult([], [], 0, 0, 0, "Footprint computation failed.")
    if not segments:
        return FootprintResult([], [], 0, 0, 0, "No supported objects.")

    result = clean_curves(
        segments,
        [0] * len(segments),
        tol,
        180.0,
        join_tol=gap_tol,
        split_touches=True,
        drop_thin=True,
    )
    curves = list(result.curves)
    curves += [_true_arc(segments[i], plane, tol) for i in result.unchanged]

    closed, polygons, open_curves = [], [], []
    for curve in curves:
        polygon = _polygon(curve, plane, tol) if curve.IsClosed else []
        if len(polygon) < 3:
            open_curves.append(curve)
            continue
        closed.append(curve)
        polygons.append(polygon)
    # A segment shorter than gap_tol may be absorbed by the node snap and
    # reported as failed although nothing is missing; anything else is kept.
    for i in list(result.failed) + list(result.skipped):
        if segments[i].GetLength() > gap_tol:
            open_curves.append(segments[i])

    areas = [_area(c, p) for c, p in zip(closed, polygons)]
    parents = nest_loops(polygons, areas)
    depths = loop_depths(parents)
    kept = keep_loops(parents, areas, min_area)
    regions = sum(1 for i in kept if depths[i] % 2 == 0)
    return FootprintResult(
        closed=[closed[i] for i in kept],
        open=open_curves,
        regions=regions,
        holes=len(kept) - regions,
        dropped=len(closed) - len(kept),
        error="",
    )

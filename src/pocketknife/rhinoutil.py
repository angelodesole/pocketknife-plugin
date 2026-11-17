"""Rhino-dependent helpers shared by Pocket Knife commands and components.

Only importable inside Rhino 8 (CPython 3.9 runtime).
"""

from __future__ import annotations

import Rhino
import Rhino.Geometry as rg

from pocketknife.geometry2d import Point2, Rect2D, rect_corners


def _curve_points(curve: rg.Curve, tolerance: float, angle_tol: float) -> list:
    ok, polyline = curve.TryGetPolyline()
    if ok:
        return list(polyline)
    approx = curve.ToPolyline(tolerance, angle_tol, 0.0, 0.0)
    if approx is None:
        return [curve.PointAtStart, curve.PointAtEnd]
    return list(approx.ToPolyline())


def _brep_mesh(geometry: rg.GeometryBase) -> rg.Mesh | None:
    if isinstance(geometry, rg.Mesh):
        return geometry
    brep = rg.Brep.TryConvertBrep(geometry)
    if brep is None:
        return None
    parts = rg.Mesh.CreateFromBrep(brep, rg.MeshingParameters.QualityRenderMesh)
    if not parts:
        return None
    mesh = rg.Mesh()
    for part in parts:
        mesh.Append(part)
    return mesh


def geometry_points(
    geometry: rg.GeometryBase, tolerance: float, angle_tol: float = 0.05
) -> list:
    """Samples points whose convex hull approximates the geometry hull.

    Args:
        geometry: Any Rhino geometry.
        tolerance: Chord tolerance for curves.
        angle_tol: Angle tolerance for curves, in radians.

    Returns:
        List of ``Rhino.Geometry.Point3d``.
    """
    if isinstance(geometry, rg.Point):
        return [geometry.Location]
    if isinstance(geometry, rg.PointCloud):
        return list(geometry.GetPoints())
    if isinstance(geometry, rg.Curve):
        return _curve_points(geometry, tolerance, angle_tol)
    if isinstance(geometry, rg.Hatch):
        points = []
        for curve in geometry.Get3dCurves(True):
            points += _curve_points(curve, tolerance, angle_tol)
        return points
    mesh = _brep_mesh(geometry)
    if mesh is not None:
        points = list(mesh.Vertices.ToPoint3dArray())
        brep = (
            None if isinstance(geometry, rg.Mesh) else rg.Brep.TryConvertBrep(geometry)
        )
        if brep is not None:
            for edge in brep.Edges:
                points += _curve_points(edge.DuplicateCurve(), tolerance, angle_tol)
        return points
    return list(geometry.GetBoundingBox(True).GetCorners())


def object_points(rhino_object: Rhino.DocObjects.RhinoObject, tolerance: float) -> list:
    """Samples points from a document object, block instances included.

    Args:
        rhino_object: Document object.
        tolerance: Chord tolerance for curves.

    Returns:
        List of ``Rhino.Geometry.Point3d`` in world coordinates.
    """
    if isinstance(rhino_object, Rhino.DocObjects.InstanceObject):
        xform = rhino_object.InstanceXform
        points = []
        for child in rhino_object.InstanceDefinition.GetObjects():
            for p in object_points(child, tolerance):
                p.Transform(xform)
                points.append(p)
        return points
    return geometry_points(rhino_object.Geometry, tolerance)


def to_xy(points) -> list[Point2]:
    """Projects ``Point3d`` objects to XY tuples."""
    return [(p.X, p.Y) for p in points]


def to_xyz(points) -> list[tuple[float, float, float]]:
    """Converts ``Point3d`` objects to tuples."""
    return [(p.X, p.Y, p.Z) for p in points]


def rect_to_rhino(rect: Rect2D, z: float = 0.0) -> rg.Polyline:
    """Converts a ``Rect2D`` to a closed Rhino polyline at height ``z``."""
    corners = [rg.Point3d(x, y, z) for x, y in rect_corners(rect)]
    return rg.Polyline(corners + [corners[0]])


def _ring(polyline) -> list[Point2]:
    ring = [(p.X, p.Y) for p in polyline]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def xy_outlines(geometry: rg.GeometryBase, tolerance: float) -> list[list[Point2]]:
    """Computes the closed outlines of a geometry projected on the XY plane.

    Args:
        geometry: Closed curve, hatch, surface, brep, extrusion, SubD or mesh.
        tolerance: Chord tolerance.

    Returns:
        Closed loops as lists of XY tuples (unsorted outer loops and holes).
    """
    curves = []
    if isinstance(geometry, rg.Curve):
        if geometry.IsClosed:
            curves = [geometry]
    elif isinstance(geometry, rg.Hatch):
        curves = list(geometry.Get3dCurves(True)) + list(geometry.Get3dCurves(False))
    if curves:
        loops = []
        for curve in curves:
            flat = rg.Curve.ProjectToPlane(curve, rg.Plane.WorldXY)
            loops.append(_ring(_curve_points(flat, tolerance, 0.05)))
        return loops

    mesh = _brep_mesh(geometry)
    if mesh is None:
        return []
    outlines = mesh.GetOutlines(rg.Plane.WorldXY) or []
    return [_ring(polyline) for polyline in outlines]


def vertical_mid_z(
    geometry: rg.GeometryBase, x: float, y: float, tolerance: float
) -> float:
    """Finds a Z value inside the geometry along the vertical line at (x, y).

    For solids it is the middle of the longest inside segment; for planar
    curves and hatches it is the height of their plane.

    Args:
        geometry: Source geometry.
        x: X coordinate.
        y: Y coordinate.
        tolerance: Intersection tolerance.

    Returns:
        The Z value; the bounding-box center height when nothing better exists.
    """
    bbox = geometry.GetBoundingBox(True)
    fallback = bbox.Center.Z
    line = rg.Line(
        rg.Point3d(x, y, bbox.Min.Z - 1.0), rg.Point3d(x, y, bbox.Max.Z + 1.0)
    )

    plane_source = None
    if isinstance(geometry, rg.Curve):
        plane_source = geometry
    elif isinstance(geometry, rg.Hatch):
        plane_source = geometry.Get3dCurves(True)[0]
    if plane_source is not None:
        ok, plane = plane_source.TryGetPlane(tolerance)
        if ok:
            ok, t = rg.Intersect.Intersection.LinePlane(line, plane)
            if ok:
                return line.PointAt(t).Z
        return fallback

    zs: list[float] = []
    if isinstance(geometry, rg.Mesh):
        hits = rg.Intersect.Intersection.MeshLine(geometry, line)
        zs = [p.Z for p in (hits or [])]
    else:
        brep = rg.Brep.TryConvertBrep(geometry)
        if brep is not None:
            ok, _, points = rg.Intersect.Intersection.CurveBrep(
                rg.LineCurve(line), brep, tolerance
            )
            if ok:
                zs = [p.Z for p in points]
    zs.sort()
    if len(zs) == 1:
        return zs[0]
    if len(zs) >= 2:
        pairs = [(zs[i], zs[i + 1]) for i in range(0, len(zs) - 1, 2)]
        low, high = max(pairs, key=lambda pair: pair[1] - pair[0])
        return (low + high) / 2.0
    return fallback

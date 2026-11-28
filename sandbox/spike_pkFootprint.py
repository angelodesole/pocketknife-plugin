#! python3
"""SPIKE (throwaway): footprint via the Make2D engine and scene silhouettes.

Run with _RunPythonScript. Selects objects, computes a parallel hidden-line
drawing along the plane normal, keeps the visible segments flagged as scene
silhouettes (surface on one side, void on the other), maps them onto the
plane and joins them with pkCleanCurves' pipeline. Prints diagnostics so we
can judge whether the approach is right. Not a command: do not ship.
"""

import os
import sys

_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _name in [m for m in sys.modules if m.split(".")[0] == "pocketknife"]:
    del sys.modules[_name]

import math
import time
from collections import Counter

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import System

from pocketknife.rhinocurves import clean_curves
from pocketknife.rhinoui import get_objects_with_options

LAYER = "pkFootprint spike"


def layer_index(doc, name, color):
    """Returns the index of a top-level layer, creating it if needed."""
    index = doc.Layers.FindByFullPath(name, -1)
    if index >= 0:
        return index
    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    layer.Color = color
    return doc.Layers.Add(layer)


def hld_geometry(obj):
    """Geometry the hidden-line engine accepts (SubD goes through a brep)."""
    geometry = obj.Geometry
    if isinstance(geometry, rg.SubD):
        return geometry.ToBrep(rg.SubDToBrepOptions.Default)
    return geometry


def parallel_viewport(plane, bbox):
    """Parallel viewport looking at the plane along its normal (-Z)."""
    vp = Rhino.DocObjects.ViewportInfo()
    vp.ChangeToParallelProjection(True)
    center = bbox.Center
    distance = max(bbox.Diagonal.Length, 1.0) * 2.0
    vp.SetCameraLocation(center + plane.ZAxis * distance)
    vp.SetCameraDirection(plane.ZAxis * -1.0)
    vp.SetCameraUp(plane.YAxis)
    vp.Extents(math.radians(20.0), bbox)
    return vp


def main():
    """Runs the spike."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects for the footprint",
        {"Plane": ("World", "CPlane"), "Raw": ("No", "Yes")},
        "pkFootprintSpike",
    )
    if picked is None:
        return
    objects, values = picked
    tol = doc.ModelAbsoluteTolerance
    if values["Plane"] == "CPlane":
        plane = doc.Views.ActiveView.ActiveViewport.ConstructionPlane()
    else:
        plane = rg.Plane.WorldXY

    t0 = time.perf_counter()
    params = rg.HiddenLineDrawingParameters()
    params.AbsoluteTolerance = tol
    params.Flatten = True
    params.IncludeHiddenCurves = False
    params.IncludeTangentEdges = False
    params.IncludeTangentSeams = False
    bbox = rg.BoundingBox.Empty
    added = 0
    for obj in objects:
        geometry = hld_geometry(obj)
        if geometry is None:
            continue
        if params.AddGeometry(geometry, rg.Transform.Identity, obj.Id):
            added += 1
            bbox.Union(geometry.GetBoundingBox(True))
    if not added:
        print("Spike: no supported geometry.")
        return
    params.SetViewport(parallel_viewport(plane, bbox))
    hld = rg.HiddenLineDrawing.Compute(params, True)
    t1 = time.perf_counter()
    if hld is None:
        print("Spike: HiddenLineDrawing.Compute failed.")
        return

    ok, to_world = hld.WorldToHiddenLine.TryGetInverse()
    flatten = rg.Transform.PlanarProjection(plane)
    visible = rg.HiddenLineDrawingSegment.Visibility.Visible
    stats = Counter()
    outline = []
    for segment in hld.Segments:
        stats["segments"] += 1
        if segment.SegmentVisibility != visible:
            stats["not visible"] += 1
            continue
        fills = segment.CurveSideFills
        key = tuple(str(f) for f in fills) if fills else ("none",)
        stats["fills " + " / ".join(key)] += 1
        if not segment.IsSceneSilhouette:
            continue
        curve = segment.CurveGeometry.DuplicateCurve()
        if ok:
            curve.Transform(to_world)
        curve.Transform(flatten)
        outline.append(curve)
    hld.Dispose()
    t2 = time.perf_counter()

    result = clean_curves(outline, [0] * len(outline), tol, 15.0)
    t3 = time.perf_counter()

    attributes = Rhino.DocObjects.ObjectAttributes()
    attributes.LayerIndex = layer_index(
        doc, LAYER, System.Drawing.Color.FromArgb(230, 80, 25)
    )
    curves = list(result.curves) + [outline[i] for i in result.unchanged]
    for curve in curves:
        doc.Objects.AddCurve(curve, attributes)
    if values["Raw"] == "Yes":
        raw = attributes.Duplicate()
        raw.LayerIndex = layer_index(
            doc, LAYER + " raw", System.Drawing.Color.FromArgb(50, 130, 230)
        )
        for curve in outline:
            doc.Objects.AddCurve(curve, raw)

    closed = sum(1 for c in curves if c.IsClosed)
    print(
        f"Spike: {added} objects -> {len(outline)} silhouette segments -> "
        f"{len(curves)} curves ({closed} closed, {len(curves) - closed} open)."
    )
    print(f"  times: HLD {t1 - t0:.2f}s, extract {t2 - t1:.2f}s, join {t3 - t2:.2f}s")
    print(f"  WorldToHiddenLine inverse ok: {ok}")
    for name, count in sorted(stats.items()):
        print(f"  {name}: {count}")
    doc.Views.Redraw()


if __name__ == "__main__":
    main()

#! python3
"""Rebuild faceted curves into lines, arcs/circles and minimal NURBS.

Pocket Knife command. Also runnable from the repository with _RunPythonScript.
For curves exported badly by Revit, SketchUp or Blender: true corners are
kept, uniformly faceted runs become real arcs and circles, straight runs
become lines, and the rest becomes smooth NURBS with the fewest control
points. Every input vertex stays within the tolerance.
"""

import os
import sys

try:
    import pocketknife  # noqa: F401  Installed with the plug-in.
except ImportError:
    # Development: run from the repository with _RunPythonScript.
    sys.path.insert(
        0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
    )

from collections import Counter

import Rhino
import scriptcontext as sc
import System

from pocketknife.rhinorebuild import control_point_count, rebuild_curve
from pocketknife.rhinoui import get_objects_with_options


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select curves to rebuild",
        {"DeleteInput": ("Yes", "No")},
        "pkRebuildCurves",
        Rhino.DocObjects.ObjectType.Curve,
        number_options={
            "Tolerance": (doc.ModelAbsoluteTolerance, 1e-6, 1e6),
            "CornerAngle": (45.0, 1.0, 179.0),
        },
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked
    tol = values["Tolerance"]

    kinds = Counter()
    before = after = failed = 0
    undo = doc.BeginUndoRecord("pkRebuildCurves")
    added = []
    for obj in objects:
        curve = obj.Geometry
        result, piece_kinds = rebuild_curve(curve, tol, values["CornerAngle"])
        if result is None:
            failed += 1
            continue
        curve_id = doc.Objects.AddCurve(result, obj.Attributes.Duplicate())
        if curve_id == System.Guid.Empty:
            failed += 1
            continue
        added.append(curve_id)
        kinds.update(piece_kinds)
        before += control_point_count(curve)
        after += control_point_count(result)
        if values["DeleteInput"] == "Yes":
            doc.Objects.Delete(obj, True)
    if undo:
        doc.EndUndoRecord(undo)

    doc.Objects.UnselectAll()
    for curve_id in added:
        doc.Objects.Select(curve_id)
    print(
        f"pkRebuildCurves: {len(added)} curves rebuilt: {kinds['line']} lines, "
        f"{kinds['arc'] + kinds['circle']} arcs/circles, {kinds['nurbs']} free; "
        f"control points {before} -> {after}; {kinds['polyline']} kept faceted."
    )
    if failed:
        print(f"  {failed} curve(s) could not be rebuilt and were kept as they are.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

#! python3
"""Draw the outline of the union of breps and meshes on a plane.

Pocket Knife prototype: run with _RunPythonScript from the repository.
The footprint of many objects seen from above (World XY or the construction
plane): one closed curve per island and per real hole, exact lines, arcs and
circles, tiny gaps closed by the gap tolerance.
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

import Rhino
import scriptcontext as sc
import System

from pocketknife.rhinofootprint import collect_geometry, footprint
from pocketknife.rhinoui import get_objects_with_options

_TYPES = Rhino.DocObjects.ObjectType
_FILTER = (
    _TYPES.Brep
    | _TYPES.Extrusion
    | _TYPES.Mesh
    | _TYPES.SubD
    | _TYPES.InstanceReference
)
_KEY = "pkFootprint"


def main():
    """Runs the command."""
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    picked = get_objects_with_options(
        "Select objects",
        {"Plane": ("World", "CPlane")},
        _KEY,
        _FILTER,
        number_options={
            "MinArea": (0.0, 0.0, 1e12),
            "GapTolerance": (3 * tol, tol, 1e6),
        },
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked
    if values["GapTolerance"] == 3 * tol:
        # Keep following the document tolerance until the user sets a value.
        sc.sticky[_KEY].pop("GapTolerance", None)

    if values["Plane"] == "CPlane" and doc.Views.ActiveView is not None:
        plane = doc.Views.ActiveView.ActiveViewport.ConstructionPlane()
    else:
        plane = Rhino.Geometry.Plane.WorldXY

    items, skipped = collect_geometry(objects)
    result = footprint(items, plane, tol, values["GapTolerance"], values["MinArea"])
    if result.error:
        print(f"pkFootprint: {result.error}")
        return Rhino.Commands.Result.Failure

    undo = doc.BeginUndoRecord("pkFootprint")
    added_closed = []
    added_open = []
    attributes = doc.CreateDefaultAttributes()
    for curves, added in ((result.closed, added_closed), (result.open, added_open)):
        for curve in curves:
            curve_id = doc.Objects.AddCurve(curve, attributes)
            if curve_id != System.Guid.Empty:
                added.append(curve_id)
    if undo:
        doc.EndUndoRecord(undo)

    doc.Objects.UnselectAll()
    for curve_id in added_open or added_closed:
        doc.Objects.Select(curve_id)
    print(
        f"pkFootprint: {len(objects)} objects -> {result.regions} regions "
        f"({len(result.closed)} curves, {result.holes} holes), "
        f"{result.dropped} small loops dropped."
    )
    if added_open:
        print(
            f"  {len(added_open)} curve(s) could not be closed and are selected: "
            "check the model there, or try another GapTolerance."
        )
    if skipped:
        print(f"  {skipped} object(s) skipped (unsupported type).")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

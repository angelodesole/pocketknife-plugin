#! python3
"""Rotate objects so their minimum XY rectangle aligns to X or Y.

Pocket Knife command. Also runnable from the repository with _RunPythonScript.
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

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

from pocketknife.geometry2d import alignment_rotation, min_bounding_rect
from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import object_points, to_xy


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects to orient",
        {"Axis": ("X", "Y"), "Group": ("No", "Yes")},
        "pkOrientToMinRect",
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    tolerance = doc.ModelAbsoluteTolerance
    sets = [objects] if values["Group"] == "Yes" else [[obj] for obj in objects]
    moved = 0
    for group in sets:
        points = []
        for obj in group:
            points += object_points(obj, tolerance)
        if not points:
            continue
        rect = min_bounding_rect(to_xy(points))
        angle = alignment_rotation(rect, values["Axis"])
        if abs(angle) < 1e-9:
            continue
        pivot = rg.Point3d(rect.center[0], rect.center[1], 0.0)
        xform = rg.Transform.Rotation(angle, rg.Vector3d.ZAxis, pivot)
        for obj in group:
            doc.Objects.Transform(obj.Id, xform, True)
            moved += 1

    print(f"pkOrientToMinRect: {moved} object(s) rotated.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

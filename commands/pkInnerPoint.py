#! python3
"""Add a point always inside each object (pole of inaccessibility on XY).

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
import scriptcontext as sc

from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import inner_points

OT = Rhino.DocObjects.ObjectType
FILTER = OT.Curve | OT.Surface | OT.Brep | OT.Extrusion | OT.Mesh | OT.Hatch | OT.SubD


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select closed curves, hatches, surfaces, polysurfaces or meshes",
        {"Z": ("Mid", "Zero"), "Regions": ("All", "Biggest")},
        "pkInnerPoint",
        object_filter=FILTER,
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    added, failed = [], 0
    for obj in objects:
        points = [
            point
            for point, _ in inner_points(
                obj.Geometry, doc.ModelAbsoluteTolerance, values["Z"], values["Regions"]
            )
        ]
        if not points:
            failed += 1
        for point in points:
            added.append(doc.Objects.AddPoint(point))

    doc.Objects.UnselectAll()
    for point_id in added:
        doc.Objects.Select(point_id)
    print(f"pkInnerPoint: {len(added)} point(s) added.")
    if failed:
        print(f"{failed} object(s) skipped: no closed outline found.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

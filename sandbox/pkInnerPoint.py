#! python3
"""Add a point always inside each object (pole of inaccessibility on XY).

Prototype: run it in Rhino 8 with _RunPythonScript (or open it in _ScriptEditor).
"""

import os
import sys

# Development bootstrap: load the shared library from ../src and always reload
# it, so edits are picked up without restarting Rhino.
_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _name in [
    m for m in sys.modules if m == "pocketknife" or m.startswith("pocketknife.")
]:
    del sys.modules[_name]

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

from pocketknife.geometry2d import group_loops_into_regions, polylabel
from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import vertical_mid_z, xy_outlines

OT = Rhino.DocObjects.ObjectType
FILTER = OT.Curve | OT.Surface | OT.Brep | OT.Extrusion | OT.Mesh | OT.Hatch | OT.SubD


def inner_points(geometry, tolerance, z_mode="Mid", regions_mode="All", precision=None):
    """Computes inner points of a geometry.

    Args:
        geometry: Closed curve, hatch, surface, brep, extrusion, SubD or mesh.
        tolerance: Document tolerance.
        z_mode: ``"Zero"`` or ``"Mid"``.
        regions_mode: ``"All"`` (one point per region) or ``"Biggest"``.
        precision: Absolute precision, None for automatic.

    Returns:
        List of ``Point3d``.
    """
    regions = group_loops_into_regions(xy_outlines(geometry, tolerance))
    if regions_mode == "Biggest":
        regions = regions[:1]
    points = []
    for rings in regions:
        x, y = polylabel(rings, precision)
        z = 0.0 if z_mode == "Zero" else vertical_mid_z(geometry, x, y, tolerance)
        points.append(rg.Point3d(x, y, z))
    return points


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
        points = inner_points(
            obj.Geometry, doc.ModelAbsoluteTolerance, values["Z"], values["Regions"]
        )
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

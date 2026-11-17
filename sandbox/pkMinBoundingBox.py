#! python3
"""Add the minimum-volume oriented bounding box of objects.

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

from pocketknife.geometry3d import min_bounding_box
from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import object_points, to_xyz


def box_to_rhino(box, tolerance):
    """Converts a ``Box3D`` to Rhino geometry.

    Args:
        box: Oriented box.
        tolerance: Below this size a box side is considered flat.

    Returns:
        A ``Brep`` for solid boxes, a closed ``PolylineCurve`` for flat ones.
    """
    center = rg.Point3d(*box.center)
    x_axis, y_axis, z_axis = (rg.Vector3d(*axis) for axis in box.axes)
    sizes = list(box.sizes)
    if min(sizes) > tolerance:
        plane = rg.Plane(center, x_axis, y_axis)
        intervals = [rg.Interval(-s / 2.0, s / 2.0) for s in sizes]
        return rg.Box(plane, *intervals).ToBrep()
    # Flat result: drop the thinnest axis and draw a rectangle.
    axes = [x_axis, y_axis, z_axis]
    order = sorted(range(3), key=lambda k: -sizes[k])
    plane = rg.Plane(center, axes[order[0]], axes[order[1]])
    rect = rg.Rectangle3d(
        plane,
        rg.Interval(-sizes[order[0]] / 2.0, sizes[order[0]] / 2.0),
        rg.Interval(-sizes[order[1]] / 2.0, sizes[order[1]] / 2.0),
    )
    return rect.ToNurbsCurve()


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects",
        {"Accuracy": ("Normal", "Fast", "Precise"), "Group": ("No", "Yes")},
        "pkMinBoundingBox",
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    tolerance = doc.ModelAbsoluteTolerance
    sets = [objects] if values["Group"] == "Yes" else [[obj] for obj in objects]
    added = []
    for group in sets:
        points = []
        for obj in group:
            points += object_points(obj, tolerance)
        if not points:
            continue
        box = min_bounding_box(to_xyz(points), values["Accuracy"])
        geometry = box_to_rhino(box, tolerance)
        if isinstance(geometry, rg.Brep):
            added.append(doc.Objects.AddBrep(geometry))
        else:
            added.append(doc.Objects.AddCurve(geometry))
        print("  {:.4f} x {:.4f} x {:.4f}".format(*sorted(box.sizes, reverse=True)))

    doc.Objects.UnselectAll()
    for item in added:
        doc.Objects.Select(item)
    print(f"pkMinBoundingBox: {len(added)} box(es) added.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

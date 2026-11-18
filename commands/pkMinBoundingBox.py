#! python3
"""Add the minimum-volume oriented bounding box of objects.

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

from pocketknife.geometry3d import CancelledError, estimated_cost, min_bounding_box
from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import object_points, to_xyz

# Above this estimated cost (about 10 s on a typical PC) the user is warned.
SLOW_COST = 5_000_000


def compute_box(points, accuracy, label):
    """Runs ``min_bounding_box`` with a status-bar progress meter.

    Shows a warning first when the computation is expected to be slow.
    Pressing Esc stops the computation.

    Args:
        points: Points as ``(x, y, z)`` tuples.
        accuracy: ``"Fast"``, ``"Normal"`` or ``"Precise"``.
        label: Text shown next to the progress meter.

    Returns:
        The ``Box3D``.

    Raises:
        CancelledError: If the user pressed Esc.
    """
    if estimated_cost(len(points), accuracy) > SLOW_COST:
        print(
            f"pkMinBoundingBox: {len(points)} points with Accuracy={accuracy}, "
            "this may take a while... (Esc to cancel, Accuracy=Fast is quicker)"
        )
    Rhino.UI.StatusBar.ShowProgressMeter(0, 100, label, True, True)
    Rhino.RhinoApp.Wait()

    def progress(fraction):
        Rhino.UI.StatusBar.UpdateProgressMeter(int(fraction * 100), True)
        Rhino.RhinoApp.Wait()
        return not sc.escape_test(False)

    try:
        return min_bounding_box(points, accuracy, progress)
    finally:
        Rhino.UI.StatusBar.HideProgressMeter()


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
        {"Accuracy": ("Normal", "Fast", "Precise"), "Group": ("Yes", "No")},
        "pkMinBoundingBox",
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    tolerance = doc.ModelAbsoluteTolerance
    sets = [objects] if values["Group"] == "Yes" else [[obj] for obj in objects]
    added = []
    for number, group in enumerate(sets, start=1):
        points = []
        for obj in group:
            points += object_points(obj, tolerance)
        if not points:
            continue
        label = f"pkMinBoundingBox {number}/{len(sets)}"
        try:
            box = compute_box(to_xyz(points), values["Accuracy"], label)
        except CancelledError:
            print("pkMinBoundingBox: cancelled.")
            break
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

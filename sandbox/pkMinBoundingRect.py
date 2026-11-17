#! python3
"""Draw the minimum bounding rectangle of objects on the XY plane.

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
import scriptcontext as sc

from pocketknife.geometry2d import min_bounding_rect
from pocketknife.rhinoui import get_objects_with_options
from pocketknife.rhinoutil import object_points, rect_to_rhino, to_xy


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects",
        {"Metric": ("Area", "Perimeter"), "Group": ("No", "Yes")},
        "pkMinBoundingRect",
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
        rect = min_bounding_rect(to_xy(points), values["Metric"])
        added.append(doc.Objects.AddPolyline(rect_to_rhino(rect, 0.0)))
        print(
            f"  {max(rect.width, rect.height):.4f} x {min(rect.width, rect.height):.4f}"
        )

    doc.Objects.UnselectAll()
    for curve_id in added:
        doc.Objects.Select(curve_id)
    print(f"pkMinBoundingRect: {len(added)} rectangle(s) added on XY.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

#! python3
"""Minimum-volume oriented bounding box.

Grasshopper component of Pocket Knife (Rhino 8, Python 3 Script component).
Inputs and outputs: see grasshopper/README.md.
"""

import sys

try:
    import pocketknife  # noqa: F401  Installed with the plug-in.
except ImportError:
    # Development: load the library from the local clone of the repository.
    sys.path.insert(0, r"C:\dev\pocketknife-plugin\src")

import Grasshopper

WARNING = Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning


def warn(message):
    """Shows a warning balloon on the component."""
    ghenv.Component.AddRuntimeMessage(WARNING, message)  # noqa: F821


def as_list(value):
    """Returns the input as a list without None items."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    return [item for item in items if item is not None]


from pocketknife.geometry3d import min_bounding_box
from pocketknife.rhinoutil import (
    box_to_rhino_box,
    document_tolerance,
    geometry_points,
    to_xyz,
)

ACCURACY = ("Fast", "Normal", "Precise")

# Inputs: G (geometry, list), U (bool, group: one box for all), A (int 0-2,
# accuracy: Fast, Normal, Precise).
geometries = as_list(G)  # noqa: F821
group = U is not False  # noqa: F821
accuracy = ACCURACY[1 if A is None else max(0, min(2, int(A)))]  # noqa: F821

tolerance = document_tolerance()
sets = [geometries] if group else [[g] for g in geometries]
B, V = [], []
for items in sets:
    points = []
    for item in items:
        points += geometry_points(item, tolerance)
    if not points:
        continue
    box = min_bounding_box(to_xyz(points), accuracy)
    B.append(box_to_rhino_box(box))
    V.append(box.volume)
ghenv.Component.Message = "{} | {}".format(  # noqa: F821
    accuracy, "Group" if group else "Each"
)

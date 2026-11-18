#! python3
"""Rotate geometry so its minimum XY rectangle aligns to X or Y.

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
import Rhino.Geometry as rg

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


from pocketknife.geometry2d import alignment_rotation, min_bounding_rect
from pocketknife.rhinoutil import document_tolerance, geometry_points, to_xy

# Inputs: G (geometry, list), Y (bool, align the long side to Y instead of X),
# U (bool, group: rotate all together).
geometries = as_list(G)  # noqa: F821
axis = "Y" if Y else "X"  # noqa: F821
group = bool(U)  # noqa: F821

tolerance = document_tolerance()
indices = (
    [list(range(len(geometries)))] if group else [[i] for i in range(len(geometries))]
)
O = [None] * len(geometries)  # noqa: E741
X = [rg.Transform.Identity] * len(geometries)
for idx in indices:
    points = []
    for i in idx:
        points += geometry_points(geometries[i], tolerance)
    if not points:
        continue
    rect = min_bounding_rect(to_xy(points))
    angle = alignment_rotation(rect, axis)
    pivot = rg.Point3d(rect.center[0], rect.center[1], 0.0)
    xform = rg.Transform.Rotation(angle, rg.Vector3d.ZAxis, pivot)
    for i in idx:
        moved = geometries[i].Duplicate()
        moved.Transform(xform)
        O[i] = moved
        X[i] = xform
ghenv.Component.Message = "{} | {}".format(  # noqa: F821
    axis, "Group" if group else "Each"
)

#! python3
"""Minimum bounding rectangle on the XY plane.

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


from pocketknife.geometry2d import AREA, PERIMETER, min_bounding_rect
from pocketknife.rhinoutil import document_tolerance, geometry_points, to_xy

# Inputs: G (geometry, list), U (bool, group: one rectangle for all),
# P (bool, minimize perimeter instead of area).
geometries = as_list(G)  # noqa: F821
group = bool(U)  # noqa: F821
metric = PERIMETER if P else AREA  # noqa: F821

tolerance = document_tolerance()
sets = [geometries] if group else [[g] for g in geometries]
R, A = [], []
for items in sets:
    points = []
    for item in items:
        points += geometry_points(item, tolerance)
    if not points:
        continue
    rect = min_bounding_rect(to_xy(points), metric)
    x_axis = rg.Vector3d(1.0, 0.0, 0.0)
    x_axis.Rotate(rect.angle, rg.Vector3d.ZAxis)
    plane = rg.Plane(
        rg.Point3d(rect.center[0], rect.center[1], 0.0),
        x_axis,
        rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, x_axis),
    )
    R.append(
        rg.Rectangle3d(
            plane,
            rg.Interval(-rect.width / 2.0, rect.width / 2.0),
            rg.Interval(-rect.height / 2.0, rect.height / 2.0),
        )
    )
    A.append(rect.width * rect.height)
ghenv.Component.Message = "{} | {}".format(  # noqa: F821
    metric, "Group" if group else "Each"
)

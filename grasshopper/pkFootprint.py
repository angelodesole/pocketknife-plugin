#! python3
"""Footprint: the outline of the union of many breps and meshes on a plane.

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
import Rhino

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


from pocketknife.rhinofootprint import collect_geometry, footprint
from pocketknife.rhinoutil import document_tolerance

# Inputs: G (geometry, list), P (plane), A (float, MinArea), T (float, gap tol).
tol = document_tolerance()
plane = Rhino.Geometry.Plane.WorldXY if P is None else P  # noqa: F821
min_area = 0.0 if A is None else max(0.0, float(A))  # noqa: F821
gap_tol = 3.0 * tol if T is None else max(tol, float(T))  # noqa: F821

items, skipped = collect_geometry(as_list(G))  # noqa: F821
result = footprint(items, plane, tol, gap_tol, min_area)
if skipped:
    warn(f"{skipped} object(s) skipped (unsupported type).")
if result.open:
    warn(f"{len(result.open)} curve(s) could not be closed.")
if result.error:
    warn(result.error)
C = list(result.closed)
O = list(result.open)
ghenv.Component.Message = (  # noqa: F821
    f"{'World' if P is None else 'Plane'} | {min_area:g}"  # noqa: F821
)

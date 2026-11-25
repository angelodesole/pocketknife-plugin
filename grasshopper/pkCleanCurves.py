#! python3
"""Clean a messy curve network: no duplicates, continuous straight joins.

Grasshopper component of Pocket Knife (Rhino 8, Python 3 Script component).
Inputs and outputs: see grasshopper/README.md.
"""

import sys

try:
    import pocketknife  # noqa: F401  Installed with the plug-in.
except ImportError:
    # Development: load the library from the local clone of the repository.
    sys.path.insert(0, r"C:\dev\pocketknife-plugin\src")

import math

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


from pocketknife.rhinocurves import clean_curves
from pocketknife.rhinoutil import document_tolerance

# Inputs: C (curves, list), A (float, max deviation angle at junctions, deg).
curves = as_list(C)  # noqa: F821
max_angle = 15.0 if A is None else max(0.0, min(90.0, float(A)))  # noqa: F821

result = clean_curves(
    curves, [0] * len(curves), document_tolerance(), max_angle, math.radians(1.0)
)
if result.skipped:
    warn(f"{len(result.skipped)} non-planar curve(s) skipped.")
C = list(result.curves) + [curves[i].DuplicateCurve() for i in result.unchanged]
ghenv.Component.Message = f"{max_angle:g}°"  # noqa: F821

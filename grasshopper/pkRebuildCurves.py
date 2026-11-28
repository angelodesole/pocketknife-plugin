#! python3
"""Rebuild faceted curves into lines, arcs/circles and minimal NURBS.

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


from pocketknife.rhinorebuild import rebuild_curve
from pocketknife.rhinoutil import document_tolerance

# Inputs: C (curves, list), T (float, tolerance), A (float, corner angle deg).
curves = as_list(C)  # noqa: F821
tolerance = document_tolerance() if T is None else max(1e-6, float(T))  # noqa: F821
corner = 45.0 if A is None else max(1.0, min(179.0, float(A)))  # noqa: F821

out, failed = [], 0
for curve in curves:
    result, _ = rebuild_curve(curve, tolerance, corner)
    if result is None:
        failed += 1
        result = curve.DuplicateCurve()
    out.append(result)
if failed:
    warn(f"{failed} curve(s) could not be rebuilt: passed through.")
C = out
ghenv.Component.Message = f"{tolerance:g} | {corner:g}°"  # noqa: F821

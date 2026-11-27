#! python3
"""Clip curves with mask shapes, like a clipping mask (even-odd rule).

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


from pocketknife.rhinoclip import clip_curves, mask_set
from pocketknife.rhinoutil import document_tolerance

# Inputs: C (curves, list), M (mask geometry, list), O (bool, keep outside).
curves = as_list(C)  # noqa: F821
keep_inside = not O  # noqa: F821

tolerance = document_tolerance()
I, X = [], []
masks = mask_set(as_list(M), tolerance, math.radians(1.0))  # noqa: F821
if masks.ignored:
    warn(f"{masks.ignored} mask object(s) ignored (open or not planar).")
if masks.error:
    warn(masks.error)
elif curves:
    result = clip_curves(curves, masks, tolerance, keep_inside)
    I = list(result.pieces) + [curves[i].DuplicateCurve() for i in result.untouched]
    X = list(result.origins) + list(result.untouched)
ghenv.Component.Message = "Inside" if keep_inside else "Outside"  # noqa: F821

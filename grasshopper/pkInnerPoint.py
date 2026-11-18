#! python3
"""Inner point of geometries: always inside, projected on XY.

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


from pocketknife.rhinoutil import document_tolerance, inner_points

# Inputs: G (geometry, item), M (bool, Z at mid height), B (bool, biggest
# region only), A (int 1-6, accuracy).
geometry = G  # noqa: F821
z_mode = "Zero" if M is False else "Mid"  # noqa: F821
regions_mode = "Biggest" if B else "All"  # noqa: F821
accuracy = 3 if A is None else max(1, min(6, int(A)))  # noqa: F821

P, D = [], []
if geometry is not None:
    results = inner_points(
        geometry, document_tolerance(), z_mode, regions_mode, 10.0**-accuracy
    )
    if not results:
        warn("No closed outline found: use closed curves, surfaces, breps or meshes.")
    P = [point for point, _ in results]
    D = [distance for _, distance in results]
ghenv.Component.Message = f"{z_mode} | {regions_mode}"  # noqa: F821

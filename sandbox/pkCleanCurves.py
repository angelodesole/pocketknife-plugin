#! python3
"""Clean a messy curve network: no duplicates, continuous straight joins.

Pocket Knife prototype: run with _RunPythonScript from the repository.
Replaces the Make2D -> SelChain -> Join routine. Overlapping and duplicated
stretches are drawn once; pieces are joined at their endpoints following the
straightest continuation, so a grid becomes long X and Y curves and an
outline stays separate from the inner lines that touch it. Collinear lines
and co-circular arcs merge; the geometry never moves beyond the tolerance.
"""

import os
import sys

_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _name in [m for m in sys.modules if m.split(".")[0] == "pocketknife"]:
    del sys.modules[_name]

import Rhino
import scriptcontext as sc
import System

from pocketknife.rhinocurves import clean_curves
from pocketknife.rhinoui import get_objects_with_options


def attribute_key(attributes):
    """Group key of an object in Layers=PerLayer mode.

    Args:
        attributes: ``Rhino.DocObjects.ObjectAttributes``.

    Returns:
        A hashable key: layer plus color, linetype and print width, each with
        its source; a value counts only when it comes from the object.
    """
    sources = Rhino.DocObjects
    from_color = attributes.ColorSource == sources.ObjectColorSource.ColorFromObject
    from_linetype = (
        attributes.LinetypeSource == sources.ObjectLinetypeSource.LinetypeFromObject
    )
    from_weight = (
        attributes.PlotWeightSource
        == sources.ObjectPlotWeightSource.PlotWeightFromObject
    )
    return (
        attributes.LayerIndex,
        str(attributes.ColorSource),
        attributes.ObjectColor.ToArgb() if from_color else None,
        str(attributes.LinetypeSource),
        attributes.LinetypeIndex if from_linetype else None,
        str(attributes.PlotWeightSource),
        round(attributes.PlotWeight, 6) if from_weight else None,
    )


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select curves",
        {"Layers": ("PerLayer", "All"), "DeleteInput": ("Yes", "No")},
        "pkCleanCurves",
        object_filter=Rhino.DocObjects.ObjectType.Curve,
        number_options={"MaxAngle": (15.0, 0.0, 90.0)},
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    curves = [obj.Geometry for obj in objects]
    if values["Layers"] == "PerLayer":
        keys = [attribute_key(obj.Attributes) for obj in objects]
    else:
        keys = [0] * len(objects)
    result = clean_curves(
        curves,
        keys,
        doc.ModelAbsoluteTolerance,
        values["MaxAngle"],
        doc.ModelAngleToleranceRadians,
    )

    undo = doc.BeginUndoRecord("pkCleanCurves")
    added = []
    keep = set(result.unchanged) | set(result.skipped) | set(result.failed)
    for curve, source, members in zip(result.curves, result.sources, result.members):
        attributes = objects[source].Attributes.Duplicate()
        curve_id = doc.Objects.AddCurve(curve, attributes)
        if curve_id == System.Guid.Empty:
            keep |= members
        else:
            added.append(curve_id)
    if values["DeleteInput"] == "Yes":
        for i, obj in enumerate(objects):
            if i not in keep:
                doc.Objects.Delete(obj, True)
    if undo:
        doc.EndUndoRecord(undo)

    doc.Objects.UnselectAll()
    for curve_id in added:
        doc.Objects.Select(curve_id)
    for i in result.unchanged:
        doc.Objects.Select(objects[i].Id)
    out_count = len(added) + len(result.unchanged)
    print(
        f"pkCleanCurves: {len(objects)} curves in -> {out_count} curves out, "
        f"{result.removed} duplicates removed, "
        f"{len(result.skipped)} skipped (non-planar)."
    )
    if result.failed:
        print(
            f"  {len(result.failed)} input curve(s) could not be rebuilt "
            "and were kept as they are."
        )
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

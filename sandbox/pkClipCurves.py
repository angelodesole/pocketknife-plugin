#! python3
"""Clip curves with mask shapes, like a clipping mask (even-odd rule).

Pocket Knife prototype: run with _RunPythonScript from the repository.
Replaces Split + Delete by boundary. Curves are cut where they cross the
mask boundaries; only the pieces inside (or outside) are kept. Stretches
lying on a mask boundary are always dropped. Nested mask shapes are holes.
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

from pocketknife.rhinoclip import clip_curves, mask_set
from pocketknife.rhinoui import get_objects_with_options

ObjectType = Rhino.DocObjects.ObjectType


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select curves to clip", {}, "pkClipCurvesCurves", ObjectType.Curve
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    targets, _ = picked
    doc.Objects.UnselectAll()
    doc.Views.Redraw()
    picked = get_objects_with_options(
        "Select mask shapes",
        {"Keep": ("Inside", "Outside"), "DeleteMask": ("No", "Yes")},
        "pkClipCurves",
        ObjectType.Curve | ObjectType.Hatch,
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    mask_objects, values = picked
    mask_ids = {obj.Id for obj in mask_objects}
    targets = [obj for obj in targets if obj.Id not in mask_ids]

    tol = doc.ModelAbsoluteTolerance
    masks = mask_set(
        [obj.Geometry for obj in mask_objects], tol, doc.ModelAngleToleranceRadians
    )
    if masks.error:
        print(f"pkClipCurves: {masks.error}")
        return Rhino.Commands.Result.Cancel
    result = clip_curves(
        [obj.Geometry for obj in targets], masks, tol, values["Keep"] == "Inside"
    )

    undo = doc.BeginUndoRecord("pkClipCurves")
    added = []
    for piece, origin in zip(result.pieces, result.origins):
        attributes = targets[origin].Attributes.Duplicate()
        added.append(doc.Objects.AddCurve(piece, attributes))
    for i in result.removed:
        doc.Objects.Delete(targets[i], True)
    if values["DeleteMask"] == "Yes":
        for obj in mask_objects:
            doc.Objects.Delete(obj, True)
    if undo:
        doc.EndUndoRecord(undo)

    doc.Objects.UnselectAll()
    for curve_id in added:
        doc.Objects.Select(curve_id)
    for i in result.untouched:
        doc.Objects.Select(targets[i].Id)
    kept = len(result.pieces) + len(result.untouched)
    dropped = len(set(result.removed) - set(result.origins))
    print(
        f"pkClipCurves: {len(targets)} curves -> {kept} pieces kept, "
        f"{dropped} dropped ({result.boundary} on boundary)."
    )
    if masks.ignored:
        print(f"  {masks.ignored} mask object(s) ignored (open or not planar).")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

#! python3
"""Clip curves with mask shapes, like a clipping mask (even-odd rule).

Pocket Knife command. Also runnable from the repository with _RunPythonScript.
Replaces Split + Delete by boundary. Curves are cut where they cross the
mask boundaries; only the pieces inside (or outside) are kept. Stretches
lying on a mask boundary are always dropped. Nested mask shapes are holes.
"""

import os
import sys

try:
    import pocketknife  # noqa: F401  Installed with the plug-in.
except ImportError:
    # Development: run from the repository with _RunPythonScript.
    sys.path.insert(
        0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
    )

import Rhino
import scriptcontext as sc
import System

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

    tol = doc.ModelAbsoluteTolerance
    masks = mask_set(
        [obj.Geometry for obj in mask_objects], tol, doc.ModelAngleToleranceRadians
    )
    if masks.error:
        print(f"pkClipCurves: {masks.error}")
        return Rhino.Commands.Result.Cancel
    # An object picked in both sets is a mask only if it gave a mask loop.
    mask_ids = {mask_objects[i].Id for i in masks.used}
    targets = [obj for obj in targets if obj.Id not in mask_ids]
    result = clip_curves(
        [obj.Geometry for obj in targets], masks, tol, values["Keep"] == "Inside"
    )

    undo = doc.BeginUndoRecord("pkClipCurves")
    added, not_added = [], set()
    for piece, origin in zip(result.pieces, result.origins):
        attributes = targets[origin].Attributes.Duplicate()
        curve_id = doc.Objects.AddCurve(piece, attributes)
        if curve_id == System.Guid.Empty:
            not_added.add(origin)
        else:
            added.append(curve_id)
    for i in result.removed:
        # Never lose geometry: keep an input if any of its pieces failed.
        if i not in not_added:
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
    kept = len(added) + len(result.untouched)
    dropped = len(set(result.removed) - set(result.origins))
    print(
        f"pkClipCurves: {len(targets)} curves -> {kept} pieces kept, "
        f"{dropped} dropped ({result.boundary} on boundary)."
    )
    if masks.ignored:
        print(f"  {masks.ignored} mask object(s) ignored (open or not planar).")
    failed = len(set(result.failed) | not_added)
    if failed:
        print(f"  {failed} curve(s) could not be clipped and were kept as they are.")
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

#! python3
"""Set layer colors from the diffuse color of the layer materials.

Prototype: run it in Rhino 8 with _RunPythonScript (or open it in _ScriptEditor).
"""

import os
import sys

# Development bootstrap: load the shared library from ../src and always reload
# it, so edits are picked up without restarting Rhino.
_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _name in [
    m for m in sys.modules if m == "pocketknife" or m.startswith("pocketknife.")
]:
    del sys.modules[_name]

import Rhino
import scriptcontext as sc
import System

from pocketknife.rhinoui import get_objects_with_options

MODES = ("Default", "Override")
ALL_LAYERS = ("No", "Yes")


def material_color(doc, layer):
    """Returns the diffuse (or PBR base) color of the layer material.

    Args:
        doc: Rhino document.
        layer: Layer to inspect.

    Returns:
        A ``System.Drawing.Color``, or None if the layer has no material.
    """
    index = layer.RenderMaterialIndex
    if index < 0:
        return None
    material = doc.Materials[index]
    if material is None:
        return None
    if material.IsPhysicallyBased:
        color = material.PhysicallyBased.BaseColor.AsSystemColor()
    else:
        color = material.DiffuseColor
    return System.Drawing.Color.FromArgb(255, color.R, color.G, color.B)


def objects_on_layer(doc, layer_index):
    """Returns every modifiable object on a layer, hidden and locked included."""
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.LayerIndexFilter = layer_index
    settings.HiddenObjects = True
    settings.LockedObjects = True
    settings.ReferenceObjects = False
    return list(doc.Objects.GetObjectList(settings))


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects (or set AllLayers=Yes and press Enter)",
        {"Mode": MODES, "AllLayers": ALL_LAYERS},
        "pkLayerColorFromMaterial",
        accept_nothing=True,
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    if values["AllLayers"] == "Yes":
        layer_indices = [layer.Index for layer in doc.Layers if not layer.IsDeleted]
    elif objects:
        layer_indices = sorted({obj.Attributes.LayerIndex for obj in objects})
    else:
        return Rhino.Commands.Result.Nothing

    updated, skipped, reset_objects = 0, [], 0
    for index in layer_indices:
        layer = doc.Layers[index]
        color = material_color(doc, layer)
        if color is None:
            skipped.append(layer.FullPath)
            continue
        layer.Color = color
        layer.CommitChanges()
        updated += 1
        if values["Mode"] == "Override":
            for obj in objects_on_layer(doc, index):
                attributes = obj.Attributes.Duplicate()
                if (
                    attributes.ColorSource
                    != Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                ):
                    attributes.ColorSource = (
                        Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                    )
                    doc.Objects.ModifyAttributes(obj, attributes, True)
                    reset_objects += 1

    message = f"pkLayerColorFromMaterial: {updated} layer(s) updated"
    if values["Mode"] == "Override":
        message += f", {reset_objects} object(s) reset to ByLayer"
    print(message + ".")
    if skipped:
        print("Skipped (no material): " + ", ".join(skipped))
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

#! python3
"""Copy or cut objects into a mirrored ' - Copy' layer structure.

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

from pocketknife.layers import (
    PARENT_MAX,
    PARENT_MIN,
    PARENT_NO,
    plan_targets,
    unique_copy_name,
)
from pocketknife.rhinoui import get_objects_with_options

COPY_CLONE = "Clone"
COPY_CUT = "Cut"


def parent_index(doc, layer_index):
    """Returns the parent layer index, or None for a root layer."""
    parent_id = doc.Layers[layer_index].ParentLayerId
    if parent_id == System.Guid.Empty:
        return None
    parent = doc.Layers.FindId(parent_id)
    return None if parent is None else parent.Index


def child_names(doc, parent_id):
    """Returns the names of the live layers under ``parent_id``."""
    return [
        layer.Name
        for layer in doc.Layers
        if not layer.IsDeleted and layer.ParentLayerId == parent_id
    ]


def add_layer_like(doc, source_index, name, parent_id):
    """Adds a layer with the attributes of another layer.

    Args:
        doc: Rhino document.
        source_index: Index of the layer to imitate.
        name: Name of the new layer.
        parent_id: Parent layer id (``Guid.Empty`` for a root layer).

    Returns:
        The index of the new layer.
    """
    source = doc.Layers[source_index]
    layer = Rhino.DocObjects.Layer()
    layer.CopyAttributesFrom(source)
    layer.Id = System.Guid.NewGuid()
    layer.Name = name
    layer.ParentLayerId = parent_id
    return doc.Layers.Add(layer)


def main():
    """Runs the command."""
    doc = sc.doc
    picked = get_objects_with_options(
        "Select objects to copy into a layer copy",
        {"Parent": (PARENT_NO, PARENT_MIN, PARENT_MAX), "Copy": (COPY_CLONE, COPY_CUT)},
        "pkCopyToLayerCopy",
    )
    if picked is None:
        return Rhino.Commands.Result.Cancel
    objects, values = picked

    full = {obj.Attributes.LayerIndex for obj in objects}
    parents = {}
    for index in full:
        current = index
        while current is not None and current not in parents:
            parents[current] = parent_index(doc, current)
            current = parents[current]
    plan = plan_targets(full, parents, values["Parent"])

    created = {}  # (anchor, original layer) -> new layer index

    def copy_of(anchor, original, parent_id, name):
        key = (anchor, original)
        if key not in created:
            created[key] = add_layer_like(doc, original, name, parent_id)
        return created[key]

    target_of = {}
    for layer_index, (anchor, chain) in plan.items():
        anchor_layer = doc.Layers[anchor]
        anchor_parent = anchor_layer.ParentLayerId
        if (anchor, anchor) not in created:
            name = unique_copy_name(anchor_layer.Name, child_names(doc, anchor_parent))
        else:
            name = None
        current = copy_of(anchor, anchor, anchor_parent, name)
        for original in chain:
            current = copy_of(
                anchor, original, doc.Layers[current].Id, doc.Layers[original].Name
            )
        target_of[layer_index] = current

    new_ids = []
    for obj in objects:
        target = target_of[obj.Attributes.LayerIndex]
        if values["Copy"] == COPY_CLONE:
            new_id = doc.Objects.Duplicate(obj.Id)
            new_obj = doc.Objects.FindId(new_id)
        else:
            new_obj = obj
        attributes = new_obj.Attributes.Duplicate()
        attributes.LayerIndex = target
        doc.Objects.ModifyAttributes(new_obj, attributes, True)
        new_ids.append(new_obj.Id)

    doc.Objects.UnselectAll()
    doc.Objects.Select(System.Collections.Generic.List[System.Guid](new_ids))
    print(
        "pkCopyToLayerCopy: {} object(s) {} into {} new layer(s).".format(
            len(new_ids),
            "copied" if values["Copy"] == COPY_CLONE else "moved",
            len(created),
        )
    )
    doc.Views.Redraw()
    return Rhino.Commands.Result.Success


if __name__ == "__main__":
    main()

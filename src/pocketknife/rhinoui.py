"""Command-line UI helpers for Pocket Knife commands (Rhino 8 only)."""

from __future__ import annotations

import Rhino
import scriptcontext as sc
from Rhino.Input import GetResult


def get_objects_with_options(
    prompt: str,
    options: dict[str, tuple[str, ...]],
    sticky_key: str,
    object_filter: Rhino.DocObjects.ObjectType = Rhino.DocObjects.ObjectType.AnyObject,
    accept_nothing: bool = False,
):
    """Asks for objects while offering list options on the command line.

    Option values are remembered between runs in ``scriptcontext.sticky``.

    Args:
        prompt: Command prompt.
        options: Option name mapped to its allowed values (first is default).
        sticky_key: Key used to remember option values.
        object_filter: Allowed object types.
        accept_nothing: If True, pressing Enter without a selection returns an
            empty object list instead of cancelling.

    Returns:
        ``(objects, values)`` where ``objects`` is a list of ``RhinoObject``
        and ``values`` maps option names to the chosen value, or ``None`` if
        the user cancelled.
    """
    stored = sc.sticky.get(sticky_key, {})
    values = {
        name: stored.get(name, allowed[0])
        if stored.get(name) in allowed
        else allowed[0]
        for name, allowed in options.items()
    }

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(prompt)
    go.GeometryFilter = object_filter
    go.GroupSelect = True
    go.SubObjectSelect = False
    go.EnablePreSelect(True, True)
    go.AcceptNothing(accept_nothing)

    while True:
        go.ClearCommandOptions()
        option_indices = {}
        for name, allowed in options.items():
            index = go.AddOptionList(name, list(allowed), allowed.index(values[name]))
            option_indices[index] = name
        result = go.GetMultiple(1, 0)
        if result == GetResult.Option:
            name = option_indices.get(go.OptionIndex())
            if name is not None:
                values[name] = options[name][go.Option().CurrentListOptionIndex]
            go.EnablePreSelect(False, True)
            continue
        if result == GetResult.Nothing and accept_nothing:
            objects = []
            break
        if result != GetResult.Object:
            return None
        objects = [go.Object(i).Object() for i in range(go.ObjectCount)]
        break

    sc.sticky[sticky_key] = dict(values)
    return objects, values

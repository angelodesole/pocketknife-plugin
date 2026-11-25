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
    number_options: dict[str, tuple[float, float, float]] | None = None,
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
        number_options: Option name mapped to ``(default, minimum, maximum)``
            for numeric options. Their values are returned as floats.

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
    number_options = number_options or {}
    for name, (default, low, high) in number_options.items():
        value = stored.get(name, default)
        values[name] = (
            float(value)
            if isinstance(value, (int, float)) and low <= value <= high
            else float(default)
        )

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
        doubles = {}
        for name, (_, low, high) in number_options.items():
            option = Rhino.Input.Custom.OptionDouble(values[name], low, high)
            index = go.AddOptionDouble(name, option)
            if isinstance(index, tuple):  # pythonnet returns ref arguments too.
                index = index[0]
            doubles[index] = (name, option)
        result = go.GetMultiple(1, 0)
        if result == GetResult.Option:
            index = go.OptionIndex()
            name = option_indices.get(index)
            if name is not None:
                values[name] = options[name][go.Option().CurrentListOptionIndex]
            elif index in doubles:
                name, option = doubles[index]
                values[name] = float(option.CurrentValue)
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

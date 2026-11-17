"""Layer-tree planning for pkCopyToLayerCopy (no Rhino dependency)."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from typing import TypeVar

K = TypeVar("K", bound=Hashable)

PARENT_NO = "No"
PARENT_MIN = "Min"
PARENT_MAX = "Max"


def ancestors(layer: K, parents: Mapping[K, K | None]) -> list[K]:
    """Returns the ancestors of a layer, nearest first."""
    result = []
    current = parents.get(layer)
    while current is not None:
        result.append(current)
        current = parents.get(current)
    return result


def plan_targets(
    full_layers: Iterable[K], parents: Mapping[K, K | None], mode: str
) -> dict[K, tuple[K, list[K]]]:
    """Plans where the selected objects of each layer are copied.

    A layer is "full" when it holds selected objects; every other layer counts
    as empty, whatever it contains, because the selection always wins.

    * ``No``: the anchor is the layer itself, copied as ``<name> - Copy``.
    * ``Min``: the anchor is the nearest empty ancestor.
    * ``Max``: the anchor is the farthest empty ancestor.

    Without an empty ancestor, ``Min`` and ``Max`` fall back to ``No``.

    A full layer below another full layer always goes inside the copy of its
    topmost full ancestor, with its original name, so the copied structure
    stays one tree in every mode.

    Args:
        full_layers: Layers holding selected objects.
        parents: Parent of each layer (``None`` for root layers).
        mode: ``PARENT_NO``, ``PARENT_MIN`` or ``PARENT_MAX``.

    Returns:
        For each full layer, ``(anchor, chain)``: the anchor is copied as a
        sibling named ``<anchor> - Copy``; ``chain`` lists the layers below the
        anchor down to the full layer, recreated with their original names
        inside the copy. ``chain`` is empty when the anchor is the layer itself.

    Raises:
        ValueError: If ``mode`` is unknown.
    """
    if mode not in (PARENT_NO, PARENT_MIN, PARENT_MAX):
        raise ValueError(f"Unknown mode: {mode}")
    full = set(full_layers)
    plan: dict[K, tuple[K, list[K]]] = {}
    nested: list[tuple[K, K, list[K]]] = []
    for layer in full:
        chain_up = ancestors(layer, parents)
        full_above = [a for a in chain_up if a in full]
        if full_above:
            # Keep the copy a single tree: follow the topmost full ancestor.
            top = full_above[-1]
            below = list(reversed(chain_up[: chain_up.index(top)])) + [layer]
            nested.append((layer, top, below))
            continue
        empty = [a for a in chain_up if a not in full]
        if mode == PARENT_NO or not empty:
            plan[layer] = (layer, [])
            continue
        anchor = empty[0] if mode == PARENT_MIN else empty[-1]
        below = chain_up[: chain_up.index(anchor)]
        plan[layer] = (anchor, list(reversed(below)) + [layer])
    for layer, top, below in nested:
        anchor, chain = plan[top]
        plan[layer] = (anchor, chain + below)
    return plan


def unique_copy_name(name: str, sibling_names: Iterable[str]) -> str:
    """Returns ``<name> - Copy``, or ``<name> - Copy N`` if already taken.

    Args:
        name: Original layer name.
        sibling_names: Names already used under the same parent.

    Returns:
        A name not in ``sibling_names`` (case-insensitive, like Rhino).
    """
    taken = {n.lower() for n in sibling_names}
    candidate = f"{name} - Copy"
    index = 2
    while candidate.lower() in taken:
        candidate = f"{name} - Copy {index}"
        index += 1
    return candidate

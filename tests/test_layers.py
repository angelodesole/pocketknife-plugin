"""Tests for pocketknife.layers, using the examples from the specification."""

import pytest

from pocketknife.layers import (
    PARENT_MAX,
    PARENT_MIN,
    PARENT_NO,
    plan_targets,
    unique_copy_name,
)

# Layer0 > LayerX ; Layer1 > Layer2 > (Layer3, Layer4) ; Layer1 > Layer5 > (Layer6,
# Layer5b, Layer7). Keys are unique ids, as Rhino layer names are not.
PARENTS = {
    "Layer0": None,
    "LayerX": "Layer0",
    "Layer1": None,
    "Layer2": "Layer1",
    "Layer3": "Layer2",
    "Layer4": "Layer2",
    "Layer5": "Layer1",
    "Layer6": "Layer5",
    "Layer5b": "Layer5",
    "Layer7": "Layer5",
}
SELECTED = ["Layer3", "Layer4", "Layer6"]


def test_parent_no():
    plan = plan_targets(SELECTED, PARENTS, PARENT_NO)
    assert plan == {name: (name, []) for name in SELECTED}


def test_parent_min():
    plan = plan_targets(SELECTED, PARENTS, PARENT_MIN)
    assert plan["Layer3"] == ("Layer2", ["Layer3"])
    assert plan["Layer4"] == ("Layer2", ["Layer4"])
    assert plan["Layer6"] == ("Layer5", ["Layer6"])


def test_parent_max():
    plan = plan_targets(SELECTED, PARENTS, PARENT_MAX)
    assert plan["Layer3"] == ("Layer1", ["Layer2", "Layer3"])
    assert plan["Layer6"] == ("Layer1", ["Layer5", "Layer6"])


def test_selection_wins_over_parent_content():
    # Layer2 holds selected objects too: it is no longer an empty container.
    plan = plan_targets(["Layer2", "Layer3"], PARENTS, PARENT_MIN)
    assert plan["Layer3"] == ("Layer1", ["Layer2", "Layer3"])
    assert plan["Layer2"] == ("Layer1", ["Layer2"])


def test_root_layer_falls_back_to_no():
    assert plan_targets(["Layer1"], PARENTS, PARENT_MAX) == {"Layer1": ("Layer1", [])}


def test_unique_copy_name():
    assert unique_copy_name("A", ["A"]) == "A - Copy"
    assert unique_copy_name("A", ["A", "a - copy", "A - Copy 2"]) == "A - Copy 3"


def test_unknown_mode():
    with pytest.raises(ValueError):
        plan_targets([], PARENTS, "Bad")


def test_parent_no_keeps_children_inside_full_parent_copy():
    # Reported bug: parent and children all selected with Parent=No.
    plan = plan_targets(["Layer2", "Layer3", "Layer4"], PARENTS, PARENT_NO)
    assert plan["Layer2"] == ("Layer2", [])
    assert plan["Layer3"] == ("Layer2", ["Layer3"])
    assert plan["Layer4"] == ("Layer2", ["Layer4"])


def test_full_ancestor_with_empty_layer_between():
    plan = plan_targets(["Layer1", "Layer3"], PARENTS, PARENT_MIN)
    assert plan["Layer1"] == ("Layer1", [])
    assert plan["Layer3"] == ("Layer1", ["Layer2", "Layer3"])

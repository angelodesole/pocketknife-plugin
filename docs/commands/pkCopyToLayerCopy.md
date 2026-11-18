# pkCopyToLayerCopy

Copies or moves the selected objects into a copy of their layer structure.

| Option | Effect |
|---|---|
| `Parent=No` | Each layer is copied next to the original as `<name> - Copy`. |
| `Parent=Min` | The nearest parent without selected objects becomes `<name> - Copy`, the layers below keep their names. |
| `Parent=Max` | The farthest parent without selected objects becomes `<name> - Copy`, the layers below keep their names. |
| `Copy=Clone` | Objects are duplicated; the copies end up selected. |
| `Copy=Cut` | Objects are moved. |

## Notes

Only selected objects count: a parent holding unselected objects is still a valid container. A selected layer below another selected layer always goes inside the copy of the upper one, so the copy is one tree. Without a valid parent, Min and Max behave like No. Existing names get `- Copy 2`, `- Copy 3`...

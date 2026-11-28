# pkFootprint

Draws the outline of the union of many objects seen along a plane: one closed curve per island and per real hole (courtyards), no inner lines, exact lines, arcs and circles. Made for figure-ground bases of masterplans cut with a laser. Works on breps, extrusions, meshes, SubDs and block instances (nested too).

| Option | Effect |
|---|---|
| `Plane=World` | Projects on World XY (default). |
| `Plane=CPlane` | Projects on the construction plane of the active view. |
| `MinArea` | Islands and holes with a smaller area are dropped, together with everything inside them (0 = off, default). |
| `GapTolerance` | Joins breaks in the outline and closes slits between buildings narrower than this distance (3x the document tolerance by default). |

## Notes

The curves are added to the current layer; the input objects are never changed. Buildings that touch or share walls merge into one region; two buildings touching only at a corner give two curves. A curve that cannot be closed is added anyway, selected and reported: check the model there, or try another `GapTolerance`. Mesh outlines stay faceted. One undo step.

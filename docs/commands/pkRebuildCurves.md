# pkRebuildCurves

Rebuilds curves exported badly by Revit, SketchUp or Blender (faceted polylines, over-dense curves): uniformly faceted runs become true arcs and circles, straight runs become lines, the rest becomes a smooth NURBS with the fewest control points. True corners are kept.

| Option | Effect |
|---|---|
| `Tolerance` | Maximum distance of every input vertex from the result (document tolerance by default). |
| `CornerAngle` | Turning angle, in degrees, above which a vertex is a corner (45 by default). Regular polygons with at most 360/CornerAngle sides stay polygons: an octagonal column stays an octagon at 45°. |
| `DeleteInput=Yes` | Replaces the input curves (default). |
| `DeleteInput=No` | Keeps the input curves. |

## Notes

Pieces that meet without a corner are tangent. Prints the number of lines, arcs and free curves and the control points before and after. A curve that cannot be rebuilt is kept as it is. One undo step.

# pkCleanCurves

Cleans a messy network of planar curves, such as Make2D output: overlapping and duplicated stretches are drawn once, pieces are joined at their endpoints along the straightest continuation, collinear lines and co-circular arcs merge. A grid becomes long X and Y curves; an outline stays separate from the inner lines that touch it.

| Option | Effect |
|---|---|
| `Layers=PerLayer` | Curves interact only with curves on the same layer and with the same object color, linetype and print width (default). |
| `Layers=All` | All selected curves are cleaned together. |
| `MaxAngle` | Maximum deviation from straight, in degrees, for joining at a junction of three or more pieces (15 by default). Where only two pieces meet they are always joined. |
| `DeleteInput=Yes` | Deletes the input curves that were replaced (default). |
| `DeleteInput=No` | Keeps the input curves. |

## Notes

The geometry never moves beyond the document tolerance. Non-planar curves are skipped and left as they are. Curves that come out unchanged are left in place; an input is never deleted unless its replacement was added. One undo step.

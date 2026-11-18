# pkMinBoundingRect

Draws the minimum bounding rectangle of the objects projected on the XY plane, at Z=0.

| Option | Effect |
|---|---|
| `Metric=Area` | Minimizes the area. |
| `Metric=Perimeter` | Minimizes the perimeter. |
| `Group=No` | One rectangle per object. |
| `Group=Yes` | One rectangle for all objects. |

## Notes

Exact for the sampled points (rotating calipers); curved geometry is sampled within the document tolerance.

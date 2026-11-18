# pkInnerPoint

Adds a point always inside each object: the pole of inaccessibility of its XY outline, i.e. the interior point farthest from the boundary.

| Option | Effect |
|---|---|
| `Z=Mid` | Z is in the middle of the object along the vertical through the point (inside solids, on the plane of planar curves). |
| `Z=Zero` | The point lies on the XY plane. |
| `Regions=All` | One point for each separate region of the outline. |
| `Regions=Biggest` | Only one point, in the largest region. |

## Notes

Accepts closed curves, hatches, surfaces, polysurfaces, extrusions, SubD and meshes. Holes are respected.

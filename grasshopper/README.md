# Grasshopper components

Each file is the code of one Rhino 8 **Script** component (Python 3). The
plug-in build turns every Script component of `pocketknife.gh` into a real
component, using its nickname, inputs and outputs.

All components go in the tab **Pocket Knife**, panel **Geometry**. Icons are in
`icons/png/<name>-24.png`.

## Setting up a component

1. Place a **Script** component, open it, choose Python 3 and paste the file.
2. Zoom in on the component and use the ⊕/⊖ buttons to add the inputs and
   outputs below. Rename them exactly as listed (right click → name).
3. On every input set the **type hint** and the **access** (item or list).
4. Set the nickname (right click on the component name).

During development the scripts load the library from
`C:\dev\pocketknife-plugin\src`; once the plug-in is installed they use the
installed copy.

## pkInnerPoint

Nickname `pkInnerPt`. Point always inside a geometry (pole of inaccessibility
of the XY outline).

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `G` | GeometryBase | item | – | Closed curve, hatch, surface, brep, SubD or mesh |
| `M` | bool | item | True | True: Z at mid height inside the object. False: Z = 0 |
| `B` | bool | item | False | True: only the biggest region. False: one point per region |
| `A` | int | item | 3 | Accuracy 1-6 (precision = size / 10^A). Use a slider 1-6 |

| Output | Meaning |
|---|---|
| `P` | Inner points |
| `D` | Distance from each point to the outline (radius of the largest inner circle) |

## pkMinBoundingBox

Nickname `pkMinBox`. Minimum-volume oriented bounding box.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `G` | GeometryBase | list | – | Geometry |
| `U` | bool | item | True | True: one box for all. False: one box per geometry |
| `A` | int | item | 1 | Accuracy: 0 Fast, 1 Normal, 2 Precise. Use a value list or slider 0-2 |

| Output | Meaning |
|---|---|
| `B` | Boxes |
| `V` | Volumes |

## pkMinBoundingRect

Nickname `pkMinRect`. Minimum bounding rectangle on the XY plane (Z = 0).

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `G` | GeometryBase | list | – | Geometry |
| `U` | bool | item | False | True: one rectangle for all. False: one per geometry |
| `P` | bool | item | False | True: minimize the perimeter. False: the area |

| Output | Meaning |
|---|---|
| `R` | Rectangles (`Rectangle3d`, local X along the rectangle width) |
| `A` | Areas |

## pkOrientToMinRect

Nickname `pkOrient`. Rotates geometry around Z so the long side of its
minimum XY rectangle is parallel to X or Y.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `G` | GeometryBase | list | – | Geometry |
| `Y` | bool | item | False | True: long side along Y. False: along X |
| `U` | bool | item | False | True: rotate all together. False: each on its own |

| Output | Meaning |
|---|---|
| `O` | Rotated geometry |
| `X` | Transformations (to apply to other geometry too) |

## pkCleanCurves

Nickname `pkCleanCrv`. Cleans a messy network of planar curves (e.g. Make2D
output): overlapping and duplicated stretches are drawn once, pieces are joined
at their endpoints following the straightest continuation, collinear lines and
co-circular arcs are merged. The geometry never moves beyond the document
tolerance. Non-planar curves are skipped with a warning.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to clean |
| `A` | float | item | 15 | Max deviation from straight at junctions, degrees (0-90) |

| Output | Meaning |
|---|---|
| `C` | Clean curves |

## pkClipCurves

Nickname `pkClip`. Clips curves with mask shapes like a clipping mask: curves
are cut where they cross the mask boundaries and only the pieces inside (or
outside) are kept. Even-odd rule: nested shapes are holes. Stretches lying on
a mask boundary are always dropped. Curves off the mask plane are clipped by
their projection along the mask normal.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to clip |
| `M` | GeometryBase | list | – | Mask shapes: closed planar curves or hatches, on one plane |
| `O` | bool | item | False | True: keep outside. False: keep inside |

| Output | Meaning |
|---|---|
| `I` | Kept pieces |
| `X` | Index in `C` of the curve each piece comes from |

## pkRebuildCurves

Nickname `pkRebuildCrv`. Rebuilds curves exported badly by Revit, SketchUp or
Blender (faceted polylines, over-dense curves): true corners are kept,
uniformly faceted runs become real arcs and circles, straight runs become
lines, the rest becomes smooth NURBS with the fewest control points. Every
input vertex stays within the tolerance; lines, arcs and NURBS that meet
without a corner are tangent.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to rebuild |
| `T` | float | item | document tolerance | Tolerance at the input vertices |
| `A` | float | item | 45 | Corner angle in degrees (1-179). Regular polygons with at most 360/A sides stay polygons (8 at 45°) |

| Output | Meaning |
|---|---|
| `C` | Rebuilt curves, one per input |

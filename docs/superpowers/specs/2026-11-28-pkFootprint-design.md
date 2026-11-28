# pkFootprint — design

Date: 2026-11-28. Status: approach A (Make2D engine) chosen; awaiting design
approval.

## Intent

Figure-ground bases for masterplan models cut with a laser. The user selects
the buildings of a masterplan (breps, extrusions, meshes, SubDs, block
instances; often meshes imported from city models; touching, overlapping,
sharing walls) and gets the exact outline of their union on a plane: one
closed curve per block of buildings, real courtyards as holes, no inner
lines. The curves go straight to the laser, so what matters is: every curve
closed, nothing drawn twice, true arcs where the source has them, and no
features too small to cut.

Today this takes Make2D + manual cleanup, or CurveBoolean, which is slow and
loses regions on coincident edges and shared walls.

## Goals

- Rhino command `pkFootprint` and Grasshopper component `pkFootprint`.
- Union outline of all selected objects, projected along the plane normal
  onto the plane: World XY (default) or the active CPlane.
- Holes are real: a courtyard gives an inner closed curve.
- Buildings that touch or overlap merge into one region. Breaks in the
  outline narrower than `GapTolerance` (endpoint to endpoint, the numerical
  noise of the engine) are joined, and a slit narrower than `GapTolerance`
  between two aligned buildings is closed: see Calls.
- `MinArea`: islands and holes whose enclosed area is below it are dropped
  (user's choice, option 2): no tiny pieces that fall out of the sheet, no
  tiny holes the laser cannot cut. Removal is by whole loops, so the
  geometry never moves.
- Every output curve closed. Any curve that stays open is reported, never
  silently output as if it were fine.
- Arcs and circles of the source (cylinders, round towers) come out as true
  `ArcCurve`s, not NURBS. Mesh outlines stay faceted, as the source.
- Scale: thousands of buildings in a few seconds (the spike: 500 objects in
  0.9 s).

## Non-goals

- Closing gaps wider than the tolerance by offsetting (option 3, rejected:
  it moves edges). Could become its own command later.
- Hatches, areas, labels or any output other than curves.
- Per-object footprints (each object separately): the command is about the
  union. A user who wants per-object footprints runs it on one object.
- Sections at a height (footprint at a cut plane): the outline is the full
  projection of the object, whatever its height.

## Anti-goals

- An open curve in the output that the user does not hear about.
- A segment drawn twice (a double laser pass).
- Inner lines (edges between touching buildings) left in the output.
- Moving geometry: outline vertices are where the engine puts them, within
  the model tolerance; `GapTolerance` only decides which ends join.
- Touching the input objects (they are never modified or deleted).

## Constraints

- Rhino 8, CPython 3.9.10. Google Python Style Guide, English names and
  docstrings, ruff clean. No numpy.
- Prototype in `sandbox/pkFootprint.py` (bootstrap from `sandbox/README.md`),
  run with `_RunPythonScript`; promotion only after the user approves it in
  Rhino. The spike `sandbox/spike_pkFootprint.py` is deleted when the
  prototype lands.
- Decision logic (loop nesting, `MinArea` filtering) in a Rhino-free module
  tested with pytest; RhinoCommon code in a Rhino-only module.
- Reuse the `pkCleanCurves` join (`rhinocurves.clean_curves`) instead of a
  new joiner.

## Calls made by Claude (check these)

- **Two tolerances in the join.** `clean_curves` today uses one `tol` for
  everything (sliver removal, overlap removal, node fusion, collinear and
  co-circular merging). It gets an extra keyword `join_tol` (default: `tol`,
  so pkCleanCurves is unchanged) used **only** to fuse endpoints into nodes;
  everything that shapes geometry keeps the model tolerance. pkFootprint
  calls it with `tol` = model tolerance and `join_tol` = `GapTolerance`.
  Mesh facets longer than `GapTolerance` are therefore kept; a piece shorter
  than `GapTolerance` collapses into its node. No vertex moves by more than
  the model tolerance except the snap of an endpoint onto its node (at most
  `GapTolerance`, which is the point of the option). This touches
  `curvegraph.py` / `rhinocurves.py`, shared with pkCleanCurves: the change is
  additive and covered by new pytest cases; the existing tests must pass
  unchanged.
- **Slits narrower than `GapTolerance` close** (revised 2026-11-28 after the
  Rhino test; first written as "thin strips stay"). Two buildings whose
  facing walls are closer than `GapTolerance` (e.g. 0.02 with tol 0.01) have
  their corners fused into common nodes by the join, so the outer outline
  already runs across the slit; the two facing walls were left as a
  degenerate two-segment loop and reported as open. They are now removed
  as a pair (`curvegraph.drop_thin_pairs`, option `drop_thin` of
  `clean_curves`): two line or arc segments joining the same two nodes with
  midpoints within `GapTolerance` cancel, and the buildings merge into one
  region. For the laser this is the useful result (such a slit cannot be
  cut), and no vertex moves beyond the endpoint snap. Limit: walls of
  different lengths (staggered buildings) do not share both nodes and are
  not cancelled; the curves stay open and are reported.
- **Corner-to-corner touch gives two loops.** Two buildings touching at a
  single point give two closed loops sharing that point, never one
  self-touching curve: each loop stays a simple closed curve (cleaner for the
  laser, and the one-point containment test stays valid). Mechanism: the join
  pairs branches as today but with no angle limit (`MaxAngle` 180°, so every
  branch at an even node gets a partner), then splits every chain at each
  node it passes twice (option `split_touches` in `curvegraph.build_chains`,
  off by default, so pkCleanCurves is unchanged). Whatever pairing was
  chosen at the node, the split gives the same simple loops, for touching
  islands and touching holes alike, without needing to know which side is
  material. Each such loop counts as its own region. (A pairing by material
  side was considered and rejected: two holes touching at a corner look
  locally the same as two islands, so any local turn rule merges one of the
  two cases.)
- **No upper limit on `GapTolerance`, neutral message.** With node fusion at
  `join_tol`, a very large value can fuse distinct corners into a cluster
  wider than allowed and leave curves open (seen in the spike at 5x). The
  open-curve message therefore says "could not be closed: check the model
  there, or try another GapTolerance", not "raise it".
- **Arc recognition.** `_to_segments` already recognizes arcs during the
  join; only the curves that come back "unchanged" (a lone closed
  silhouette, such as a cylinder) need `TryGetArc` / `TryGetCircle`
  afterwards.

## Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Make2D engine (`HiddenLineDrawing`) in a parallel view along the plane normal; keep visible scene-silhouette segments; join with `clean_curves` at `GapTolerance`; nesting + `MinArea` in pure Python | Fast, same path for breps and meshes, inner lines never appear; the engine sometimes leaves gaps of 1-3x tol, and a gap wider than `GapTolerance` leaves an open curve, which is reported | **Chosen** |
| B | Per-object outline (`Silhouette.Compute`, `Mesh.GetOutlines`) + `Curve.CreateBooleanRegions` on clusters of nearby objects | Every outline closed from the start, but slower on thousands of buildings, and CurveBoolean is fragile exactly on coincident edges and shared walls, where it loses regions silently | Rejected |
| C | A, with B as a fallback only for clusters left open | Most robust, but two engines to maintain and test in Rhino for a rare case | Deferred: add later if open curves turn out frequent on real masterplans |

## Spike findings (2026-11-28, tolerance 0.01 mm)

- 11 mixed objects: overlapping boxes, a courtyard block, cylinders, a mesh
  sphere, a mesh box overlapping a brep box, two boxes 0.0005 apart: all
  regions right (areas checked), courtyard hole present, sub-tolerance gap
  merged, cylinders exact circles.
- 500 breps (400 boxes, 100 cylinders, random overlaps): 1612 silhouette
  segments, HLD 0.76 s, extract 0.05 s, join 0.09 s. CurveBooleanUnion of
  the already known exact outlines: 0.30 s (but in real use the outlines are
  not known).
- At model tolerance 4 curves out of 202 stay open: the engine leaves gaps of
  0.013-0.03 at some junctions (a cylinder silhouette meeting a box edge).
  Joining at 3x tol closes all of them; at 5x two reopen, because
  `clean_curves` refuses a node cluster wider than its tolerance. Point
  sampling (3000 points) against the true union: no mismatch at 3x.
- Silhouette segments are recognized by `IsSceneSilhouette` (fills
  `SideSurface / SideVoid` either way round); `WorldToHiddenLine` inverts.

## Pipeline

1. **Collect** (Rhino). For each selected object, the geometry the engine
   accepts, with its transform: breps, extrusions, meshes directly; SubD
   through `ToBrep`; block instances exploded recursively, multiplying the
   instance transforms (masterplans often use blocks). Unsupported objects
   (curves, points, annotations…) are skipped and counted.
2. **Hidden-line drawing** (Rhino). `HiddenLineDrawingParameters` with
   `Flatten`, no hidden curves, no tangent edges or seams, absolute tolerance
   = model tolerance; a parallel `Rhino.DocObjects.ViewportInfo` looking
   along `-plane.ZAxis`, up = `plane.YAxis`, framing the union bounding box.
3. **Extract** (Rhino). Visible segments with `IsSceneSilhouette`, mapped
   back with the inverse of `WorldToHiddenLine`, then projected onto the
   plane (`Transform.PlanarProjection`).
4. **Join** (Rhino, extended). `clean_curves(segments, same key, model tol,
   180°, join_tol=GapTolerance, split_touches=True)`, see Calls. Every resulting curve is new: unlike pkCleanCurves, the
   "unchanged" inputs are output too (they are new silhouette curves, not
   document objects).
5. **True arcs** (Rhino). Arcs are recognized inside the join already; the
   "unchanged" curves (a lone closed silhouette, such as a cylinder, which
   the spike returned as a NURBS circle) become `ArcCurve`s when
   `TryGetCircle` / `TryGetArc` succeeds within model tolerance.
6. **Nesting and MinArea** (pure Python, new module). Input per closed loop:
   its enclosed area and a polygon approximation (Rhino side: `ToPolyline`
   within tol, or a fixed sample count). Loops of a union outline never
   cross, so one point per loop decides containment. Build the containment
   tree (parent = smallest loop containing it); depth even = island
   (material), odd = hole. Drop every loop with area < `MinArea` together
   with its whole subtree (a dropped island takes its holes with it; a
   dropped hole is filled, and the islands inside it would sit on solid
   material, so they go too). Area = the loop's own enclosed area, not net
   of its holes.
7. **Output** (Rhino). Closed curves added to the current layer, on the
   plane, in one undo record; the input objects are untouched. Open curves
   (if any) are added too, so no geometry is lost, but they are what ends up
   selected, with a warning (see below).

## Rhino command

```
pkFootprint
Select objects ( Plane=World  MinArea=0  GapTolerance=0.03 ):
```

- Objects: breps, extrusions, meshes, SubDs, block instances; pre-selection
  allowed.
- `Plane=World|CPlane`: World XY, or the active viewport's construction
  plane.
- `MinArea`: number, model units², default 0 (off).
- `GapTolerance`: number, model units, default 3x the model absolute
  tolerance; minimum = model tolerance.
- Options sticky, as in the other commands (`MinArea` and `GapTolerance` are
  stored as values; the default `GapTolerance` follows the document
  tolerance until the user sets one).
- End, all closed: selects the result, prints
  `pkFootprint: N objects -> R regions (C curves, H holes), D small loops dropped.`
- End, some open: selects only the open curves and prints
  `  K curve(s) could not be closed and are selected: check the model there, or try another GapTolerance.`
- Skipped objects: `  S object(s) skipped (unsupported type).`
- Nothing usable selected, or the engine fails: a message, nothing added.

## Grasshopper component

Nickname `pkFootprint`.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `G` | GeometryBase | list | – | Breps, meshes, SubDs, extrusions |
| `P` | Plane | item | World XY | Projection plane |
| `A` | float | item | 0 | MinArea: loops with a smaller area are dropped |
| `T` | float | item | 3x document tolerance | Gap tolerance |

| Output | Meaning |
|---|---|
| `C` | Closed footprint curves (islands and holes) |
| `O` | Curves that could not be closed (warning when not empty) |

`ghenv.Component.Message` shows the plane name and `MinArea` as the other
components do. Tolerance from `rhinoutil.document_tolerance()`.

## Tests

Pure Python (pytest):

- `join_tol`: ends 2x tol apart join with `join_tol` = 3x tol and stay apart
  without it; a segment longer than `join_tol` is kept, one shorter than
  `join_tol` collapses into its node;
  all existing curvegraph tests unchanged.
- `split_touches`: two squares touching corner to corner give two loops;
  two holes touching at a corner inside an island give three loops; two
  squares touching at a corner at a skew angle give two loops; default off
  leaves today's result unchanged.

- Nesting: disjoint squares; square in square (hole); three levels
  (island in a hole in an island); siblings at the same depth.
- `MinArea`: small island dropped; small hole dropped and its inner island
  with it; big island with small hole keeps the island, drops the hole;
  `MinArea=0` drops nothing; a loop exactly at `MinArea` is kept.

Rhino checklist (for the user):

1. A real masterplan (meshes from a city model, or the user's own breps):
   one closed curve per block, courtyards as holes, no inner lines.
2. Buildings sharing walls and buildings 0.005 apart: one region each.
   Buildings 2x tol apart: one region. Two buildings touching at a corner:
   two loops sharing the point.
3. A round tower: an exact circle (`ArcCurve`).
4. `MinArea` on a model with small courtyards and kiosks: they disappear,
   nothing else changes.
5. Block instances (nested), and `Plane=CPlane` with a rotated CPlane.
6. A case with an open curve (low `GapTolerance`): it is selected and
   reported.
7. Undo; the GH component on the same objects.
8. Timing on the biggest masterplan available.

## Left to the builder

- Module and function names (suggested: `footprint.py` pure, `rhinofootprint.py`
  Rhino side).
- How the loop polygons are sampled for the containment test, as long as it
  stays within tolerance of the curve.
- How block instances are flattened (recursion depth limit, linked blocks).
- Output layer handling beyond "current layer".

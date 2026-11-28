# pkCleanCurves — design

Date: 2026-11-25. Status: approach C (hybrid) chosen; grouping option A chosen; awaiting design approval.

## Intent

Replace the manual Make2D → `SelChain` → `Join` routine. Given a messy network
of fragmented, duplicated and overlapping planar curves, return continuous
curves with the fewest control points possible **without moving the geometry**.
The output feeds laser cutting (no double passes, continuous paths) and 2D
drawings (lines stay on their layer, hidden lines stay distinguishable).

## Goals

- Remove exact duplicates and partial overlaps: every stretch of geometry is
  drawn exactly once.
- Merge consecutive collinear line segments into one line and consecutive arcs
  with the same center and radius into one arc.
- Join pieces into continuous curves following the "straightest continuation"
  rule at junctions: a grid becomes long X and Y curves, an outline is not
  joined to inner lines that touch it.
- Rhino command `pkCleanCurves` and Grasshopper component `pkCleanCrv`.

## Non-goals

- Refitting free curves into smoother NURBS with fewer points. That is a
  separate command (curve rebuild), designed later; it takes this command's
  output as input.
- 3D (non-planar) curves: skipped with a warning, never deleted.
- Splitting curves at crossings or at T junctions. Joins happen only at
  endpoints; an endpoint landing on the interior of another curve is not a node
  (an unsplit outline edge stays whole, which is the wanted result).
- Closing small gaps between endpoints farther apart than the tolerance.

## Anti-goals

- Any change of shape beyond the document tolerance.
- Joining branches at random at multi-branch nodes (the defect of `Join`).
- Silently merging curves of different layers in the default mode.

## Constraints

- Rhino 8, CPython 3.9.10. Google Python Style Guide, English names and
  docstrings.
- Prototype in `sandbox/pkCleanCurves.py` (bootstrap from `sandbox/README.md`),
  run with `_RunPythonScript`; after approval move to `commands/`.
- Pure-Python logic goes in `src/pocketknife/` and is unit-tested with pytest
  in CI (no Rhino). RhinoCommon code goes in `rhinoutil.py`.
- Tolerance: document absolute tolerance; angle tolerance: document angle
  tolerance for "collinear" and "tangent" tests.

## Calls made by Claude (check these)

- **Planes.** Curves are grouped also by plane: coplanar curves (same plane
  within tolerance) form a group and are processed in that plane's 2D
  coordinates. `curvegraph.py` therefore works on 2D tuples only; Rhino code
  maps each group to and from its plane. Make2D output is one XY plane, so in
  practice one group per layer.
- **Never move geometry beyond tolerance, even at the cost of fewer merges.**
  Collinear merge: all intermediate vertices must lie within absolute
  tolerance of the merged line (not just angle tests). Co-circular merge: same
  rule on center and radius. Node fusion: no chaining; a cluster is accepted
  only if its diameter is within tolerance, otherwise endpoints stay separate.
  Segments are snapped to the node centre only within that tolerance.
- **Overlaps across kinds.** Line/line and arc/arc overlaps analytic in pure
  Python; any pair involving a `free` segment (e.g. a line lying on a degree-1
  NURBS) goes through RhinoCommon. When two overlapping copies differ in
  attributes, the copy of the longer original curve survives.
- **DeleteInput.** Skipped (non-planar) curves are never deleted. Inputs that
  come out unchanged (nothing merged, joined or removed) are left in place,
  not deleted and re-added; they count in `M`.

## Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | RhinoCommon only: `Curve.JoinCurves`, `Curve.Simplify`, duplicate removal | Little code, but `JoinCurves` picks branches at random at multi-branch nodes | Rejected |
| B | Pure Python for everything | Fully testable, but overlaps between free NURBS curves are hard to do reliably | Rejected |
| C | Hybrid: pure-Python graph and pairing, RhinoCommon for overlaps and curve assembly | Decision logic testable and predictable; heavy geometry done by Rhino | **Chosen** |

## Pipeline

Per group of curves (one group per layer, or one group for all layers):

1. **Explode and filter** (Rhino). Explode polycurves/polylines into segments.
   Skip non-planar curves (warning with count). Each segment is classified as
   `line`, `arc` (incl. full circles) or `free` (anything else).
2. **Overlap removal** (Rhino). Find overlapping stretches between segments
   (`Intersection.CurveCurve` overlap events, tolerance = doc tolerance).
   Keep one copy of each overlapping stretch; split the others at overlap
   boundaries and drop the duplicated parts. Exact duplicates are the trivial
   case. For lines and arcs this can be done analytically in pure Python
   (interval overlap on a shared line / circle); for `free` use RhinoCommon.
3. **Merge fragments** (pure Python). Consecutive collinear lines sharing an
   endpoint, and consecutive co-circular arcs sharing an endpoint, become one
   segment — only through nodes of degree 2 (a node where a third branch
   arrives is a real junction and must stay a split point for step 5).
4. **Node graph** (pure Python). Endpoints within tolerance are fused into
   nodes (spatial hashing on a grid of cell = tolerance, check neighbours).
   Each segment is an edge; each edge end stores its unit tangent leaving the
   node (from Rhino for `free`, analytic for lines/arcs).
5. **Pairing at nodes** (pure Python).
   - Degree 2: always pair (corners of an outline are joined).
   - Degree ≥ 3: compute deviation from straight for every pair of branches
     (angle between tangent of A and reversed tangent of B). Greedy: take the
     pair with the smallest deviation, if ≤ `MaxAngle`; remove both; repeat.
     Remaining branches end at the node.
   - Degree 1: open end.
6. **Chain walk** (pure Python). Follow pairings from open ends, then the
   remaining cycles (closed curves). Output: ordered list of (segment, reversed)
   per chain, plus `closed` flag.
7. **Assembly** (Rhino). Each chain becomes a `Polyline` if all segments are
   lines, else a `PolyCurve`; closed chains are closed. Line + line through a
   degree-2 node at an angle stays a polyline vertex (exact).

## Rhino command

```
pkCleanCurves
Select curves ( Layers=PerLayer  MaxAngle=15  DeleteInput=Yes ):
```

- `Layers=PerLayer` (default): groups by layer **and** by object-level
  display attributes (object color, linetype, print width, each with its
  source: by layer / by object). A visible and a hidden stretch on the same
  layer are never merged, joined or treated as overlapping. Output keeps the
  group's layer and attributes. (Decided by the user, option A.)
- `Layers=All`: one group, attributes ignored; each output curve takes the
  layer and attributes of the longest segment of its chain.
- Grouping key in both modes also includes the plane (see Calls).
- `MaxAngle`: degrees, number option, sticky. `rhinoui.get_objects_with_options`
  supports only list options today: extend it with number options
  (`AddOptionDouble`) without breaking existing callers.
- `DeleteInput=Yes`: delete the input curves. `No`: keep them.
- End: select the new curves, print `pkCleanCurves: N curves in -> M curves out,
  K duplicates removed, S skipped (non-planar).`
- One undo record for the whole operation.

## Grasshopper component

Nickname `pkCleanCrv`, tab Pocket Knife, panel Geometry (or a new Curve panel,
builder's call).

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to clean |
| `A` | float | item | 15 | Max deviation angle at junctions, degrees |

| Output | Meaning |
|---|---|
| `C` | Clean curves |

No layers in Grasshopper: the whole list is one group.

## Library placement

- `src/pocketknife/curvegraph.py` (new, pure Python): node fusion, fragment
  merge for lines/arcs, overlap of lines/arcs, pairing, chain walk. Data in as
  plain tuples (segment kind, endpoints, tangents, arc center/radius/angles),
  out as chains of segment indices. Tests in `tests/test_curvegraph.py`.
- `src/pocketknife/rhinoutil.py`: explode/classify, overlap removal for free
  curves, conversion to/from the plain data, assembly.

## Tests (pytest, pure Python)

- Grid 3×3 of fragmented lines with duplicates → 3 X curves + 3 Y curves.
- Rectangle outline with inner lines touching it in T → 1 closed outline +
  inner lines.
- Cross (degree 4) at 90° → 2 straight curves.
- Y junction (3 branches at 120°, MaxAngle=15) → 3 separate curves.
- Collinear chain of 40 segments → 1 line.
- Arc split in 5 co-circular pieces → 1 arc; full circle in pieces → 1 closed circle.
- Partial overlap of two collinear lines → union drawn once.
- Endpoint fusion within tolerance and not beyond.

## Left to the builder

- Exact data structures in `curvegraph.py`.
- Tie-breaking in greedy pairing (deterministic, e.g. by edge index).
- Whether lines/arcs overlap goes analytic or through RhinoCommon, as long as
  tests cover it.
- Icon (`icons/svg/pkCleanCurves.svg`, same style as the others), docs page
  `docs/commands/pkCleanCurves.md`, README table row.

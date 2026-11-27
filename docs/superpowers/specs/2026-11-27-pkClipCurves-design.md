# pkClipCurves — design

Date: 2026-11-27. Status: approach B (hybrid) chosen; awaiting design approval.

## Intent

A clipping mask for curves, like Illustrator's: a tangle of curves is cut by
one or more closed mask shapes and only the pieces **inside** (or only those
**outside**) are kept. It replaces Rhino's `Split` + `Delete by boundary`
routine, which is slow on big tangles and unreliable where curves are
tangent to or run along the mask boundary. Output goes to 2D drawings and
laser cutting.

## Goals

- Rhino command `pkClipCurves` and Grasshopper component `pkClip`.
- Even-odd rule over all mask loops (user's choice, "like Illustrator"):
  a point is inside if an odd number of mask loops contain it. Nested shapes
  are holes; overlapping shapes cancel in their common part.
- `Keep=Inside` (default) or `Keep=Outside`.
- Pieces lying **on** a mask boundary (overlapping it within tolerance) are
  **always dropped**, in both modes (user's choice: the boundary already
  exists in the mask; keeping it would mean a double laser pass).
- Exact: curves are only split at intersection parameters; geometry never
  moves. Pieces not longer than the tolerance are dropped.
- Fast on big tangles: each curve is intersected only with the masks whose
  bounding boxes it touches.

## Non-goals

- Clipping surfaces, meshes, hatches or text (only curves are clipped).
- Closing or joining the resulting pieces (that is `pkCleanCurves`' job).
- Non-zero or other fill rules.

## Anti-goals

- Keeping a stretch that runs along the mask boundary.
- Moving geometry, or approximating curves to split them.
- Silently clipping against masks on different planes.

## Constraints

- Rhino 8, CPython 3.9.10. Google Python Style Guide, English names and
  docstrings, ruff clean.
- Prototype in `sandbox/pkClipCurves.py` (bootstrap from `sandbox/README.md`),
  run with `_RunPythonScript`; promotion to `commands/` and the plug-in only
  after the user approves it in Rhino.
- Pure-Python logic in `src/pocketknife/` (no Rhino import), tested with
  pytest in CI. RhinoCommon code in a Rhino-only module.
- Tolerance: document absolute tolerance; angle tolerance: document angle
  tolerance.

## Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Native: `Curve.Split` against all masks, midpoint `Contains` per piece | Little code, but same weaknesses as Split + Delete by boundary on tangent/overlapping stretches; every curve against every mask | Rejected |
| B | Hybrid: Rhino gives exact intersection events (crossings and overlap intervals) with a bounding-box prefilter, and exact containment; pure Python does the interval logic | On-boundary stretches come from exact overlap events, not from a probe; decision logic testable; fast | **Chosen** |
| C | Region booleans on the mask | Rhino region booleans need closed curves; the clipped curves are mostly open | Rejected |

## Masks

- Selected objects: closed planar curves and hatches (outer and inner loops
  of a hatch all count as loops). Open or non-planar curves selected as masks
  are ignored with a warning.
- All mask loops must be coplanar (same plane within tolerance and angle
  tolerance). If not, the command stops with a message naming the problem;
  nothing is changed.
- The mask plane is the plane of the first mask loop.

## Clipping

For every curve to clip:

1. **Projection.** If the curve lies in the mask plane (within tolerance),
   use it as is. Otherwise work on a projected copy along the mask normal:
   `curve.ToNurbsCurve()` transformed by `Transform.PlanarProjection(plane)`.
   An affine transform of a NURBS keeps its parameterization, so parameters
   found on the copy are valid on the original. If the projection is
   degenerate (a curve parallel to the normal: projected length ≤ tol), the
   curve is classified as a whole by its projected point and kept or dropped
   whole.
2. **Candidates.** Only masks whose bounding box (in plane coordinates,
   expanded by tol) intersects the curve's projected bounding box.
3. **Events.** `Intersection.CurveCurve(projected, mask, tol, tol)` for each
   candidate. Crossing/touching events give split parameters (`ParameterA`).
   Overlap events give "on boundary" intervals (`OverlapA`).
4. **Intervals (pure Python).** Given the curve domain, the sorted split
   parameters and the overlap intervals, produce the pieces: maximal
   parameter intervals between consecutive splits, with overlap intervals
   removed and their ends added as splits. Each piece is tagged
   `on_boundary` (inside an overlap interval) or not.
5. **Classification.** For each piece not on the boundary, take the point at
   the middle of its parameter interval (on the projected copy) and count
   the candidate mask loops that contain it (`Curve.Contains(point, plane,
   tol)`, `Inside` result). Odd → inside. A probe point that Rhino reports as
   `Coincident` with a mask is a numerical edge case: probe again at the
   quarter and three-quarter parameters and take the majority; if still
   undecided, treat the piece as on the boundary (dropped).
6. **Keep.** Pieces whose state matches `Keep` and that are longer than tol
   are trimmed from the **original** curve (`curve.Trim(interval)`). No
   re-joining is needed, since splits exist only at mask events. Closed
   curves: a kept piece spanning the seam becomes one curve.

## Rhino command

```
pkClipCurves
Select curves to clip:
Select mask shapes ( Keep=Inside  DeleteMask=No ):
```

- Curves to clip: curve filter, pre-selection allowed. Mask shapes: curves
  and hatches. An object picked in both sets counts as a mask only.
- Each kept piece is added with the attributes of its original curve; the
  original curves that were split or dropped are deleted. Curves entirely
  kept without any split are left untouched (not deleted and re-added).
- `DeleteMask=Yes` deletes the mask objects.
- One undo record. Selects the result. Prints
  `pkClipCurves: N curves -> M pieces kept, D dropped (B on boundary).`
- Options are sticky, as in the other commands.

## Grasshopper component

Nickname `pkClip`.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to clip |
| `M` | GeometryBase | list | – | Mask shapes: closed planar curves or hatches |
| `O` | bool | item | False | True: keep outside. False: keep inside |

| Output | Meaning |
|---|---|
| `I` | Kept pieces |
| `X` | Index in `C` of the curve each piece comes from |

Warnings as balloons (non-coplanar masks, ignored masks).

## Library placement

- `src/pocketknife/intervals.py` (new, pure Python): piece building from a
  domain, split parameters and overlap intervals (with closed-curve seam
  handling), even-odd decision, keep filter. Tests in
  `tests/test_intervals.py`.
- `src/pocketknife/rhinoclip.py` (new, Rhino only): mask loop extraction,
  coplanarity check, projection, bounding-box prefilter, intersection events,
  containment, trimming.

## Tests (pytest, pure Python)

- One crossing in the middle → two pieces.
- Overlap interval in the middle → two pieces off boundary + one on boundary.
- Overlap touching the domain end → piece on boundary at the end.
- Split parameters closer than tol (in length terms, the caller passes
  lengths or a parameter tolerance) fuse into one split.
- Closed curve: piece spanning the seam is joined into one.
- Even-odd: counts 0, 1, 2, 3 → outside, inside, outside, inside.
- Keep filter with Inside/Outside; on-boundary pieces never kept.

## Left to the builder

- Exact data structures in `intervals.py`, and whether length tolerance is
  checked in pure Python (passing piece lengths) or in Rhino.
- Bounding-box prefilter structure (sorted sweep or grid).
- Icon, docs page `docs/commands/pkClipCurves.md`, README row (at promotion).

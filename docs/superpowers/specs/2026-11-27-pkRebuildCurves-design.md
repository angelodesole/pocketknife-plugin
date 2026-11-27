# pkRebuildCurves — design

Date: 2026-11-27. Status: approach B (pure Python) chosen; awaiting design approval.

## Intent

Recover clean curves from geometry exported badly by Revit, SketchUp or
Blender, where circles, arcs and free curves arrive as faceted polylines
(typically mesh edges), or as curves with far too many points. The output is
a clean starting point for modelling: real lines, real arcs and circles, and
smooth NURBS with the fewest control points. It is not meant for laser
preparation.

## Goals

- Rhino command `pkRebuildCurves` and Grasshopper component `pkRebuildCrv`.
- Find what each stretch "wanted to be":
  - **line** where the vertices lie on a straight line;
  - **arc / circle** where they lie on a circle (a SketchUp 24-gon becomes a
    true circle with the right centre and radius);
  - **smooth NURBS** with the fewest control points elsewhere.
- **True corners are kept exactly**. They are told apart from facets by a
  break in the rhythm of edge lengths and turning angles, not only by the
  angle, with an adjustable angle as backup. This works for coarse SketchUp
  circles (15° per facet at 24 segments, 30° at 12) and for fine Revit or
  Blender tessellations (2–5°).
- **Tolerance is measured at the input vertices**, not along the input edges
  (in a faceted circle the vertices lie on the true circle and the edges cut
  the chord).
- Consecutive smooth pieces join with tangent continuity (G1); corners keep
  their angle.

## Non-goals

- Extracting edges from meshes (Rhino's `DupEdge`, `DupBorder`, or Make2D
  followed by `pkCleanCurves` do that).
- Joining separate curves (that is `pkCleanCurves`).
- G2 continuity, or arcs-and-lines output for CAM.
- New dependencies such as numpy: the plug-in ships pure Python.

## Anti-goals

- Rounding off a true corner.
- A vertex of the input farther than the tolerance from the output.
- Turning a smooth free curve into a chain of tiny arcs or lines.
- More control points than needed, when a lower count meets the tolerance.

## Constraints

- Rhino 8, CPython 3.9.10. Google Python Style Guide, English names and
  docstrings, ruff clean.
- Prototype in `sandbox/pkRebuildCurves.py`, run with `_RunPythonScript`;
  promotion only after the user approves it in Rhino.
- All the analysis and fitting in pure Python (`src/pocketknife/`), tested
  with pytest in CI. Rhino code only reads vertices and builds the output
  curves.

## Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Rhino only: `Curve.Simplify` + `Curve.Fit` | `Simplify` does not see a circle in a polyline (each edge already is a line); `Fit` leaves many points | Rejected |
| B | Pure Python: corner detection, line/circle fitting on vertices, own least-squares cubic B-spline fit with fixed ends and end tangents, minimum control point search | Full control over point count and continuity, all testable; more code (a small linear solver) | **Chosen** |
| C | Pure-Python segmentation, free stretches rebuilt by Rhino's `Curve.Rebuild(n, 3, …)` with increasing `n` | Less code, but uniform point distribution and weak end-tangent control: approximate joins, more points than needed | Rejected |

## Pipeline

All in 3D coordinates; planes are computed per run where needed.

1. **Vertices** (Rhino). Polylines, degree-1 NURBS and polycurves made of
   lines: their vertices. Other curves: split at C1 discontinuities (each is
   a corner), and sample each smooth span with `ToPolyline` at a chord
   tolerance of `tol / 10`. Duplicate consecutive vertices (closer than
   `tol / 100`) are removed. Closed curves are passed as closed vertex rings.
2. **Corners** (pure Python). At every interior vertex compute the turning
   angle `a_i`. With `m_i = max(a_{i-1}, a_{i+1})` (the neighbouring facet
   angles), the vertex is a corner if:
   - `a_i ≥ CornerAngle` (default 45°, option), or
   - the rhythm breaks: `a_i - m_i ≥ 5°` and `a_i ≥ 2 · m_i`. A facet among
     regular facets turns like its neighbours; a true corner stands out.
     Example: a true 20° corner where two SketchUp arcs with 15° facets meet
     turns 35°: 35 − 15 = 20 ≥ 5 and 35 ≥ 30, so it is a corner.
   - the vertex is the end of an open curve.

   Edge lengths are not used for corners: a tangent join between a straight
   run and a faceted arc also changes edge length, and its angle is about
   half a facet, so it is not a corner.
3. **Primitives** (pure Python). A primitive must look like what exporters
   write, not just fit: exporters put line and arc vertices exactly on the
   primitive and tessellate arcs **uniformly**, while dense samples of a free
   curve fit tiny arcs and lines everywhere. So:
   - **line run**: at least 2 edges with every interior turning angle
     ≤ 0.1° and every vertex within `PRIMITIVE_FIT · tol` of the segment
     between the run's ends; or a single edge bounded on both sides by
     corners or primitives.
   - **arc run**: at least 4 vertices, sweep ≥ 20°, **regular facets** (all
     interior edge lengths and turning angles within 2 % of the run's mean;
     the first and last edge may be shorter), planar within
     `PRIMITIVE_FIT · tol`, every vertex within `PRIMITIVE_FIT · tol` of the
     fitted circle.
   - **arc fit with tangent joins**: if a neighbour of the arc is a line
     joined without a corner, the centre lies on that line's normal at the
     join (1D search); with lines on both sides it is the intersection of
     the two normals. Otherwise the centre is found on the perpendicular
     bisector of the run's ends. Lines and arcs that meet without a corner
     are therefore tangent (G1).
   - **circle**: a closed stretch without corners whose vertices pass the
     arc test (regular, planar, fit) as a whole.
   - `PRIMITIVE_FIT = 0.1`.
   - **Order of the partition**: the greedy partition starts at a corner.
     On a closed ring without corners it first tries the circle; if that
     fails it starts at the vertex where the turning angle changes most
     (`|a_i - a_{i-1}|` largest: a line-to-arc transition on a rounded
     rectangle), so no primitive is cut in two.
   - Vertices not taken by a primitive form **free runs**. A free run of a
     single edge becomes a line.
4. **Free runs: NURBS fit** (pure Python).
   - Cubic, clamped, ends interpolate the run's end vertices exactly.
   - End tangents: where the neighbour is a line or an arc joined without a
     corner, the direction is fixed to the neighbour's tangent (G1). At a
     corner the direction is free.
   - Parameterization: centripetal. Knots: averaging of the parameters
     (de Boor), which keeps the least-squares system well posed.
   - Least squares on all the run's vertices with these constraints, solved
     by a small dense solver.
   - Control points `n` start at 4 and grow by one until every vertex is
     within `tol` of the curve (distance from each vertex to the curve,
     refined with a few Newton steps from its fit parameter), up to the
     run's vertex count.
   - **Fallbacks**, in order: retry without the end tangent constraints;
     runs of 3 vertices become a quadratic through them; if nothing passes,
     the run stays a polyline (exact) and is counted as "kept faceted" in
     the summary line.
   - A **closed curve with no corner** that is not a circle and has no
     primitive is opened at the vertex of largest turning angle and fitted
     as one run, with the same tangent direction imposed at both ends (G1 at
     the seam).
5. **Output** (Rhino). One curve per input: a `LineCurve`, an `ArcCurve`, a
   `NurbsCurve`, or a `PolyCurve` of them, closed if the input was closed.
   Pieces share their end vertices exactly.

## Rhino command

```
pkRebuildCurves
Select curves to rebuild ( Tolerance=0.01  CornerAngle=45  DeleteInput=Yes ):
```

- `Tolerance`: number, default the document absolute tolerance, sticky.
  (Exports are often coarser: the user raises it.)
- `CornerAngle`: degrees, 1–179, default 45, sticky.
- `DeleteInput=Yes/No`.
- The output keeps the attributes of its input. One undo record. Prints
  `pkRebuildCurves: N curves rebuilt: L lines, A arcs/circles, F free;
  control points P -> Q; K kept faceted.`

## Grasshopper component

Nickname `pkRebuildCrv`.

| Input | Type hint | Access | Default | Meaning |
|---|---|---|---|---|
| `C` | Curve | list | – | Curves to rebuild |
| `T` | float | item | doc tolerance | Tolerance at the input vertices |
| `A` | float | item | 45 | Corner angle, degrees |

| Output | Meaning |
|---|---|
| `C` | Rebuilt curves, one per input |

## Library placement

- `src/pocketknife/polyfit.py` (new, pure Python): corners, line/arc/circle
  fits, partition into runs, B-spline evaluation, constrained least-squares
  fit, minimum control point search. Plain tuples in and out; the result per
  curve is a list of pieces: `("line", p0, p1)`, `("arc", p0, pmid, p1)`,
  `("circle", center, normal, radius, start_point)`, `("nurbs", degree,
  control_points, knots)`. Tests in `tests/test_polyfit.py`.
- Reuse `geometry3d` helpers (vectors, principal axes) for run planes.
- `src/pocketknife/rhinorebuild.py` (new, Rhino only): vertex extraction,
  building Rhino curves from pieces.

## Tests (pytest)

- SketchUp-like 24-gon and 12-gon → one circle, centre and radius within
  1e-6 of the generator.
- Rounded rectangle (4 lines + 4 faceted quarter arcs, tangent joins, 6
  facets per arc) → 8 pieces: 4 lines and 4 arcs, no corners.
- Rectangle with a true 10° corner on a long side, sides finely faceted →
  the 10° vertex is a corner.
- Fine sampling (200 points) of a free cubic → 1 NURBS with ≤ 8 control
  points, every vertex within tol.
- Free run between two lines with tangent joins → its end tangents match
  the lines within the angle tolerance.
- Every test checks the anti-goal: all input vertices within tol of output.
- Minimum control points: the count found is the smallest that passes
  (the count minus one fails).

## Left to the builder

- Exact data structures, the Newton refinement details, the solver choice.
- Planarity test details (best-fit plane via principal axes).
- Icon, docs page, README row (at promotion).

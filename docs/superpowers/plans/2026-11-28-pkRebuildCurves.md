# pkRebuildCurves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild faceted or over-dense curves into real lines, arcs/circles and minimal smooth NURBS, keeping true corners and every input vertex within tolerance.

**Architecture:** Everything that decides goes in `src/pocketknife/polyfit.py` (pure Python, pytest): corners, primitive runs, constrained least-squares cubic B-spline fit with a minimum control-point search, and the assembly of the pieces. `src/pocketknife/rhinorebuild.py` only reads vertices from Rhino curves and builds Rhino curves from the pieces. The sandbox command and the GH script are thin front ends.

**Tech Stack:** CPython 3.9.10 (Rhino 8), RhinoCommon, pytest, ruff. No numpy.

**Spec:** `docs/superpowers/specs/2026-11-27-pkRebuildCurves-design.md`

## Global Constraints

- Python 3.9, Google style, English names, ruff clean. `polyfit.py` imports no Rhino and no numpy.
- Every input vertex must be within `tol` of the output (checked in every end-to-end test).
- `PRIMITIVE_FIT = 0.1`. Corner rule: `a ≥ CornerAngle` (default 45°), or `a - m ≥ 5°` and `a ≥ 2·m` with `m` = max neighbouring turning angle.
- A line run needs ≥ 2 edges with interior turns ≤ 0.1°. An arc run needs ≥ 4 vertices, sweep ≥ 20°, regular facets (interior edges and interior turns within 2 % of their mean), planarity and fit within `PRIMITIVE_FIT·tol`.
- NURBS: cubic, clamped, ends interpolated, centripetal parameters, knots by averaging (Piegl–Tiller 9.68–9.69). The search returns the smallest passing control-point count. Fallbacks, in order: no tangent constraints, then a quadratic for 3 vertices, then a polyline.
- Prototype in `sandbox/`; promotion out of this plan.

## Review Focus

- **Collinear vertices inside a free curve** (an inflection): they must not become a line run unless the turning angles are ≤ 0.1°. Test in Task 4 (free cubic with an inflection stays 1 NURBS).
- **Very short runs (2–3 vertices) between corners:** a line for 2 vertices, a quadratic or polyline for 3, and never an exception. Test in Task 3.
- **Duplicate consecutive vertices** from exports: they give zero-length edges and an undefined turning angle. Removed first; test in Task 1.
- **Closed ring whose seam vertex sits mid-arc:** the circle must still come out as one circle. Test in Task 4 (24-gon starting at an arbitrary vertex).
- **Large inputs** (500-vertex free run): the control-point search must use doubling plus bisection, not a linear scan, to stay under 2 s. Test in Task 3.

---

### Task 1: Vectors, turning angles, corners

**Files:** Create `src/pocketknife/polyfit.py`, `tests/test_polyfit.py`

**Interfaces — Produces:**
- `Vec3 = tuple[float, float, float]`
- `dedupe(points: Sequence[Vec3], closed: bool, eps: float) -> list[Vec3]`: removes consecutive duplicates (and the closing duplicate of a closed ring).
- `turning_angles(points: Sequence[Vec3], closed: bool) -> list[float]`: radians per vertex; open ends get 0.
- `find_corners(points: Sequence[Vec3], closed: bool, corner_angle: float) -> list[int]`: sorted corner indices (radians in, rule above). Open curves always include `0` and `len-1`.

- [ ] Step 1, tests:
  - `test_dedupe_removes_repeats_and_closing_point`: `[(0,0,0),(0,0,0),(1,0,0),(1,1,0),(0,0,0)]`, closed=True, eps=1e-9 → `[(0,0,0),(1,0,0),(1,1,0)]`.
  - `test_turning_angles_square`: unit square ring → four angles of `pi/2`.
  - `test_regular_24gon_has_no_corners`.
  - `test_octagon_all_corners_at_45`: `find_corners(octagon, True, radians(45))` → all 8.
  - `test_true_20_degree_corner_between_coarse_arcs`: two arcs with 15° facets meeting at a 20° corner, so the vertex turns 35° → that vertex is a corner, the others are not.
  - `test_tangent_join_line_arc_is_not_corner`: a line of 3 edges followed by a 6-facet quarter arc → no interior corners.
- [ ] Step 2: run them and see them fail. Step 3: implement. Step 4: run, see them pass, run ruff. Step 5: commit `Add polyfit corners`.

### Task 2: Primitive runs and partition

**Files:** Modify `polyfit.py`, `tests/test_polyfit.py`

**Interfaces — Produces:**
- `class Run(NamedTuple)`: `kind: str` (`"line"|"arc"|"circle"|"free"`), `start: int`, `end: int` (vertex indices, inclusive, cyclic for rings), `center: Vec3 | None`, `normal: Vec3 | None`, `radius: float | None`.
- `best_plane(points) -> tuple[Vec3, Vec3, float]`: centroid, unit normal (the axis of least spread from `geometry3d.principal_axes`), and the maximum distance of the points from that plane.
- `fit_circle(points, plane_normal) -> tuple[Vec3, float]`: least-squares (Kåsa) circle in the plane.
- `partition(points, closed, tol, corners) -> list[Run]`: covers every edge once, in order. Each stretch between corners is processed greedily. At each start, take the longest valid line run and the longest valid arc run, and choose the one covering more vertices (ties go to the line). If neither exists, the edge joins a free run. A closed ring without corners first tries `circle`. If that fails, the partition starts at `argmax |a_i - a_{i-1}|`. A single-edge free run becomes a line.

- [ ] Step 1, tests:
  - `test_24gon_is_one_circle`: center and radius within 1e-6.
  - `test_12gon_is_one_circle`.
  - `test_rounded_rectangle_four_lines_four_arcs`: 4 lines (3 edges each) and 4 quarter arcs (6 facets), tangent joins → 8 runs alternating line and arc.
  - `test_dense_free_cubic_has_no_primitives`: 200 centripetal-irregular samples of `(t, t**3 - t, 0)` for t in [-1.5, 1.5] → all `free` (one run).
  - `test_irregular_facets_not_an_arc`: points on a circle with edge lengths alternating 1 and 1.3 → not an arc.
- [ ] Steps 2–5 as in Task 1. Commit `Add primitive runs and partition`.

### Task 3: Constrained B-spline fit

**Files:** Modify `polyfit.py`, `tests/test_polyfit.py`

**Interfaces — Produces:**
- `bspline_point(degree, ctrl, knots, u) -> Vec3` (Cox–de Boor).
- `fit_free(points: Sequence[Vec3], tol: float, t_start: Vec3 | None, t_end: Vec3 | None) -> tuple[str, tuple]`. Returns `("nurbs", (degree, ctrl, knots))` with the minimum control-point count, or `("polyline", (points,))` as a last resort. `t_start`/`t_end` are unit tangent directions, or None when free. Unknowns: free interior control points (3 each), plus a scalar α for each constrained end (`P1 = P0 + α·t_start`, `P[n-2] = P[n-1] - β·t_end`). Normal equations are solved by Gaussian elimination with partial pivoting. Distance check: Newton on `(C(u) - Q)·C'(u)` with central-difference derivatives, 5 iterations, clamped to [0, 1]. The search over n uses doubling from 4, then bisection, then a check that n-1 fails (step down if not).
- `max_deviation(points, degree, ctrl, knots) -> float`.

- [ ] Step 1, tests:
  - `test_fit_free_cubic_few_points`: 200 samples of the cubic above, tol=0.001 → nurbs, ≤ 8 control points, `max_deviation ≤ tol`.
  - `test_fit_is_minimal`: refit with n-1 control points (an exposed helper `fit_with(points, n, t_start, t_end)`) gives `max_deviation > tol`.
  - `test_end_tangents_respected`: with `t_start=(1,0,0)`, `ctrl[1]-ctrl[0]` is parallel to x within 1e-9.
  - `test_three_points_quadratic`, `test_two_points_line` (returns `("nurbs", degree 1)`), never raise.
  - `test_large_run_speed`: 500 samples, < 2 s.
- [ ] Steps 2–5. Commit `Add constrained least-squares B-spline fit`.

### Task 4: Assembly

**Files:** Modify `polyfit.py`, `tests/test_polyfit.py`

**Interfaces — Produces:**
- `Piece = tuple[str, tuple]`:
  - `("line", (p0, p1))`
  - `("arc", (p0, pmid, p1))`
  - `("circle", (center, normal, radius, start))`
  - `("nurbs", (degree, ctrl, knots))`
  - `("polyline", (points,))`
- `rebuild(points: Sequence[Vec3], closed: bool, tol: float, corner_angle: float) -> list[Piece]`. The pipeline is `dedupe(eps=tol/100)` → `find_corners` → `partition`, then the arcs are refitted with tangent constraints. A line neighbour with no corner puts the centre on the line's normal at the join; lines on both sides put it at the intersection of the normals. A constrained fit is accepted only if every vertex is within `tol`; otherwise the unconstrained fit is kept. Free runs go to `fit_free`, with tangents taken from non-corner neighbours. A closed ring that is all free is opened at its largest turn, with the same tangent at both ends. Pieces share their end vertices exactly, and each arc passes through its run's end vertices.

- [ ] Step 1, tests (each also asserts that every input vertex is within tol of the sampled output):
  - `test_rebuild_24gon_from_arbitrary_seam` → `[("circle", …)]`.
  - `test_rebuild_rounded_rectangle` → 8 pieces, each line–arc join tangent within 0.5°.
  - `test_rebuild_free_cubic_with_inflection` → 1 nurbs.
  - `test_rebuild_square_keeps_corners` → 4 lines.
  - `test_rebuild_line_then_free` → line + nurbs, tangent at the join within 0.5°.
- [ ] Steps 2–5. Commit `Add rebuild assembly`.

### Task 5: Rhino adapter, sandbox command, GH script

**Files:** Create `src/pocketknife/rhinorebuild.py`, `sandbox/pkRebuildCurves.py`, `grasshopper/pkRebuildCurves.py`; modify `grasshopper/README.md`.

**Interfaces:**
- `curve_vertices(curve, tol) -> list[tuple[list[Vec3], bool]]`: polyline, degree-1 NURBS and line-only polycurve vertices as they are. Other curves are split at C1 kinks (`GetNextDiscontinuity(Continuity.C1_continuous, …)`) and each span is sampled with `ToPolyline(0, 0, 0, 0, 0, tol / 10, 0, 0, True)`. The spans are joined into one vertex list, so kinks become corners naturally.
- `pieces_to_curve(pieces, closed) -> rg.Curve | None`. Pieces map to `LineCurve`, `ArcCurve(Arc(p0, pmid, p1))`, `ArcCurve(Circle(Plane(center, x, y), r))` (with x toward the start), `NurbsCurve` (from control points and Rhino knots, i.e. the full knot vector without its first and last value) and `PolylineCurve`. A `PolyCurve` is built if there is more than one piece, checking every `Append` and `IsValid`; the function returns None on failure.
- `count_points(curve) -> int`: control points of the curve as Rhino sees it, for the summary line.
- Command: options `Tolerance` (number, default `doc.ModelAbsoluteTolerance`, range 1e-6..1e6), `CornerAngle` (45, 1–179), `DeleteInput=Yes/No`, sticky key `pkRebuildCurves`. Build the curves first. Add each one with its input's attributes; delete the input only if the add succeeded. Use one undo record. Print the summary line from the spec. Failures are kept and counted.
- GH: inputs `C` (Curve, list), `T` (float, default doc tolerance), `A` (float, default 45); output `C`, one curve per input (the input itself if the rebuild fails, with a warning).

- [ ] Step 1: implement. Step 2: ruff and the full pytest suite green. Step 3: commit and push `Add pkRebuildCurves sandbox prototype and Grasshopper script`. Step 4: hand over the Rhino checklist: a SketchUp circle import, a Revit fine curve, a rounded rectangle, an octagon column, an over-dense NURBS (FitCrv output), undo.

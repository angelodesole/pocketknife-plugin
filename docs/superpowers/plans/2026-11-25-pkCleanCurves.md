# pkCleanCurves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Rhino command and a Grasshopper component that turn fragmented, duplicated, overlapping planar curves into continuous curves with the fewest control points, without moving the geometry.

**Architecture:** Pure-Python graph logic in `src/pocketknife/curvegraph.py` (2D, tested with pytest in CI). The Rhino adapter in `src/pocketknife/rhinocurves.py` explodes the curves, groups them by plane and attributes, removes overlaps that involve free curves, converts segments to and from the plain data, and assembles the output curves. The sandbox command and the GH script are thin front ends over `rhinocurves.clean_curves`.

**Tech Stack:** CPython 3.9.10 (Rhino 8), RhinoCommon, pytest, ruff (Google docstrings).

**Spec:** `docs/superpowers/specs/2026-11-25-pkCleanCurves-design.md`

## Global Constraints

- Python 3.9 syntax (`from __future__ import annotations`, no `match`), Google Python Style Guide, English names and docstrings, ruff clean (`uvx ruff check .`, `uvx ruff format --check .`).
- `curvegraph.py` must not import Rhino.
- Never move geometry beyond the absolute tolerance. Fewer merges or joins is acceptable; drift is not.
- Joins happen only at endpoints. Never split at crossings or T junctions.
- Default `MaxAngle` = 15°. Options: `Layers=PerLayer/All`, `MaxAngle`, `DeleteInput=Yes/No`.
- Non-planar curves are skipped with a warning and never deleted.
- Workflow: prototype in `sandbox/` with the bootstrap from `sandbox/README.md`, run with `_RunPythonScript`. Promote to `commands/` and the plug-in only after the user approves it in Rhino (Task 8).

## Review Focus

- **Slivers:** Make2D leaves segments shorter than the tolerance. Drop them before building the graph, or they create fake nodes that block pairing. Test in Task 1.
- **Already-clean input:** a single whole circle, or a polyline that needs no change, must come out with the same geometry and be flagged unchanged, so the command leaves the object alone. Tests in Tasks 3 and 6.
- **Closed loop through one node:** a closed curve split into two pieces meets at two degree-2 nodes and must become one closed curve, not two open ones. A single closed segment has the same node at both ends and is a closed chain by itself. Test in Task 3.
- **Scale:** a Make2D of a building has thousands of segments. Overlap search and node fusion must use a spatial grid (cell size = max(tolerance, the length of the longest bounding box diagonal / 256)), not O(n²) over all pairs. Test in Task 2: 2,000 random segments in under 2 s.
- **Line collinear with an arc chord:** a line and an arc that share an endpoint are never merged and never treated as an overlap. Test in Task 4.

---

### Task 1: Segment model and endpoint fusion

**Files:**
- Create: `src/pocketknife/curvegraph.py`
- Test: `tests/test_curvegraph.py`

**Interfaces:**
- Produces:
  - `Point2 = tuple[float, float]`, `Vec2 = tuple[float, float]`
  - `LINE, ARC, FREE = "line", "arc", "free"`
  - `class Segment(NamedTuple)`: `kind: str`, `start: Point2`, `end: Point2`, `t_start: Vec2` (unit tangent at the start, pointing into the segment), `t_end: Vec2` (unit tangent at the end, pointing into the segment, i.e. the reversed derivative), `length: float`, `center: Point2 | None = None`, `radius: float | None = None`, `ccw: bool | None = None` (arcs: direction from start to end), `source: int = -1` (index of the input curve, set by the adapter).
  - `line_segment(start, end, source=-1) -> Segment`
  - `arc_segment(center, radius, start_angle, sweep, source=-1) -> Segment` (sweep is signed, in radians; a full circle has `start == end`)
  - `drop_slivers(segments, tol) -> list[Segment]`: removes segments with `length <= tol`.
  - `fuse_endpoints(points: Sequence[Point2], tol: float) -> list[int]`: a node id per point.

- [ ] **Step 1: Write the failing tests**

```python
def test_line_segment_tangents_point_inward():
    s = line_segment((0, 0), (2, 0))
    assert s.t_start == pytest.approx((1, 0)) and s.t_end == pytest.approx((-1, 0))
    assert s.length == pytest.approx(2)

def test_arc_segment_quarter_ccw():
    s = arc_segment((0, 0), 1.0, 0.0, math.pi / 2)
    assert s.start == pytest.approx((1, 0)) and s.end == pytest.approx((0, 1))
    assert s.t_start == pytest.approx((0, 1)) and s.t_end == pytest.approx((1, 0))
    assert s.length == pytest.approx(math.pi / 2) and s.ccw

def test_drop_slivers():
    segs = [line_segment((0, 0), (1, 0)), line_segment((1, 0), (1.0005, 0))]
    assert drop_slivers(segs, 0.001) == segs[:1]

def test_fuse_endpoints_within_tolerance():
    ids = fuse_endpoints([(0, 0), (0.0004, 0), (5, 5), (5, 5.0003)], 0.001)
    assert ids[0] == ids[1] and ids[2] == ids[3] and ids[0] != ids[2]

def test_fuse_endpoints_no_chaining():
    # 0 - 0.0008 - 0.0016: neighbours within tol, cluster diameter beyond it.
    ids = fuse_endpoints([(0, 0), (0.0008, 0), (0.0016, 0)], 0.001)
    assert len(set(ids)) >= 2
```

- [ ] **Step 2: Run and see them fail.** `uv run --no-project --python 3.9 --with pytest pytest tests/test_curvegraph.py -v`. Expected: ImportError.
- [ ] **Step 3: Implement.** `fuse_endpoints`: hash the points into grid cells of size `tol`. Process points in input order. Each point joins the first existing cluster in the 3×3 neighbouring cells whose every member is within `tol` of it; otherwise it starts a new cluster. That keeps the cluster diameter within `tol` and the result deterministic.
- [ ] **Step 4: Run the tests, see them pass, and run ruff.**
- [ ] **Step 5: Commit** `Add curvegraph segment model and endpoint fusion`.

### Task 2: Overlap removal for lines and arcs

**Files:** Modify `src/pocketknife/curvegraph.py`, `tests/test_curvegraph.py`

**Interfaces:**
- Produces: `remove_overlaps(segments: list[Segment], tol: float) -> tuple[list[Segment], int]`. It returns the cleaned segments and the number of removed stretches. `FREE` segments pass through untouched; the adapter handles them in Task 6. Lines: group by supporting line (direction within angle derived from `tol`/length, distance within `tol`), project to 1D intervals, keep the union, and split it back at every original endpoint so no node is lost. Arcs: the same on (center, radius) within `tol`, using angular intervals. When stretches overlap, the kept piece takes the `source` of the longer original segment.

- [ ] **Step 1: Write the failing tests**

```python
def test_exact_duplicate_removed():
    a = line_segment((0, 0), (4, 0), source=0)
    out, n = remove_overlaps([a, line_segment((4, 0), (0, 0), source=1)], 0.001)
    assert sum(s.length for s in out) == pytest.approx(4) and n == 1

def test_partial_overlap_drawn_once_and_endpoints_kept():
    out, _ = remove_overlaps([line_segment((0, 0), (3, 0)), line_segment((2, 0), (5, 0))], 0.001)
    assert sum(s.length for s in out) == pytest.approx(5)
    xs = sorted({p[0] for s in out for p in (s.start, s.end)})
    assert xs == pytest.approx([0, 2, 3, 5])

def test_parallel_lines_beyond_tolerance_kept():
    out, n = remove_overlaps([line_segment((0, 0), (3, 0)), line_segment((0, 0.01), (3, 0.01))], 0.001)
    assert len(out) == 2 and n == 0

def test_arc_overlap():
    a = arc_segment((0, 0), 2, 0, math.pi)
    b = arc_segment((0, 0), 2, math.pi / 2, math.pi)
    out, _ = remove_overlaps([a, b], 0.001)
    assert sum(s.length for s in out) == pytest.approx(2 * math.pi * 1.5)

def test_overlap_scales():
    rng = random.Random(1)
    segs = [line_segment((rng.uniform(0, 1000), rng.uniform(0, 1000)),
                         (rng.uniform(0, 1000), rng.uniform(0, 1000))) for _ in range(2000)]
    t = time.perf_counter(); remove_overlaps(segs, 0.001)
    assert time.perf_counter() - t < 2.0
```

- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement** with buckets keyed by quantized line parameters (angle mod π, signed offset) and arc parameters (center, radius). Compare only within neighbouring buckets.
- [ ] **Step 4: Run the tests, see them pass, and run ruff.**
- [ ] **Step 5: Commit** `Add overlap removal for lines and arcs`.

### Task 3: Pairing at nodes and chain walk

**Files:** Modify `src/pocketknife/curvegraph.py`, `tests/test_curvegraph.py`

**Interfaces:**
- Consumes: `Segment`, `fuse_endpoints`.
- Produces:
  - `class Chain(NamedTuple)`: `items: list[tuple[int, bool]]` (segment index and reversed flag), `closed: bool`.
  - `build_chains(segments: list[Segment], tol: float, max_angle: float) -> list[Chain]` (`max_angle` in radians). Node degree 2: always pair. Degree ≥ 3: greedy on the deviation `angle(t_a, -t_b)`, smallest first, accepted if ≤ `max_angle`. Ties are broken by (smaller segment index, smaller end index). Walk from unpaired ends first, then from the remaining edges in index order (cycles → `closed=True`). Output is deterministic.

- [ ] **Step 1: Write the failing tests** (helper `grid(n, size, pieces)` makes an n×n grid of lines along X and Y, each split into `pieces` collinear segments and broken at every crossing)

```python
def test_grid_joins_along_x_and_y():
    chains = build_chains(grid(3, 10.0, 4), 0.001, math.radians(15))
    assert len(chains) == 6 and not any(c.closed for c in chains)

def test_outline_not_joined_to_inner_t():
    segs = rectangle_edges(0, 0, 10, 6) + [line_segment((5, 0), (5, 3))]
    chains = build_chains(segs, 0.001, math.radians(15))
    assert sorted((c.closed, len(c.items)) for c in chains) == [(False, 1), (True, 5)]

def test_cross_gives_two_straight_curves():
    segs = [line_segment((0, 0), (1, 0)), line_segment((1, 0), (2, 0)),
            line_segment((1, -1), (1, 0)), line_segment((1, 0), (1, 1))]
    assert len(build_chains(segs, 0.001, math.radians(15))) == 2

def test_y_junction_splits():
    segs = [line_segment((0, 0), (math.cos(a), math.sin(a))) for a in (0, 2.0944, 4.1888)]
    assert len(build_chains(segs, 0.001, math.radians(15))) == 3

def test_two_arcs_make_closed_circle():
    segs = [arc_segment((0, 0), 1, 0, math.pi), arc_segment((0, 0), 1, math.pi, math.pi)]
    (c,) = build_chains(segs, 0.001, math.radians(15))
    assert c.closed and len(c.items) == 2

def test_single_closed_segment_is_closed_chain():
    (c,) = build_chains([arc_segment((0, 0), 1, 0, 2 * math.pi)], 0.001, math.radians(15))
    assert c.closed and c.items == [(0, False)]
```

`rectangle_edges` splits the bottom edge at x=5, so the T node has degree 3.

- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests, see them pass, and run ruff.**
- [ ] **Step 5: Commit** `Add straightest-continuation pairing and chain walk`.

### Task 4: Compact chains (merge collinear lines and co-circular arcs)

**Files:** Modify `src/pocketknife/curvegraph.py`, `tests/test_curvegraph.py`

**Interfaces:**
- Produces: `compact_chain(segments: list[Segment], chain: Chain, tol: float) -> list[Segment]`. It returns the chain's segments oriented and in order, with consecutive mergeable runs merged. Lines merge only if every intermediate vertex lies within `tol` of the merged line. Arcs merge only if centres and radii agree within `tol`, the direction is the same, and every intermediate vertex lies within `tol` of the merged arc. A closed chain also tries to merge across its seam (a circle in pieces becomes one closed arc of sweep 2π). `FREE` segments never merge. The merged segment keeps the `source` of its longest part.

This plan merges after the chain walk, not before the graph as the spec's step 3 does. A straight pair through a node with 3 or more branches still belongs to one chain, so a grid line of 40 pieces becomes one line. The spec's intent, keeping junction nodes for pairing, holds because pairing has already happened.

- [ ] **Step 1: Write the failing tests**

```python
def test_forty_collinear_become_one_line():
    segs = [line_segment((i, 0), (i + 1, 0)) for i in range(40)]
    (chain,) = build_chains(segs, 0.001, math.radians(15))
    (line,) = compact_chain(segs, chain, 0.001)
    assert line.kind == LINE and line.length == pytest.approx(40)

def test_drift_beyond_tolerance_not_merged():
    # Every vertex 0.0008 higher: each joint is near-collinear, the end drifts by 0.0032.
    segs = [line_segment((i, 0.0008 * i), (i + 1, 0.0008 * (i + 1))) for i in range(4)]
    (chain,) = build_chains(segs, 0.001, math.radians(15))
    out = compact_chain(segs, chain, 0.001)
    assert all(abs(p[1] - 0.0008 * p[0]) < 1e-9 for s in out for p in (s.start, s.end))

def test_arc_pieces_merge_and_circle_closes():
    segs = [arc_segment((0, 0), 1, i * 2 * math.pi / 5, 2 * math.pi / 5) for i in range(5)]
    (chain,) = build_chains(segs, 0.001, math.radians(15))
    (arc,) = compact_chain(segs, chain, 0.001)
    assert arc.kind == ARC and arc.length == pytest.approx(2 * math.pi)

def test_line_and_arc_never_merge():
    segs = [line_segment((-1, 0), (1, 0)), arc_segment((0, 0), 1, 0, math.pi)]
    (chain,) = build_chains(segs, 0.001, math.radians(15))
    assert len(compact_chain(segs, chain, 0.001)) == 2

def test_rectangle_keeps_four_corners():
    segs = rectangle_edges(0, 0, 10, 6)
    (chain,) = build_chains(segs, 0.001, math.radians(15))
    assert len(compact_chain(segs, chain, 0.001)) == 4
```

- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite (`pytest`) and ruff, and see them pass.**
- [ ] **Step 5: Commit** `Merge collinear lines and co-circular arcs inside chains`.

### Task 5: Number options in the command UI

**Files:** Modify `src/pocketknife/rhinoui.py`

**Interfaces:**
- Produces: `get_objects_with_options(prompt, options, sticky_key, object_filter=..., accept_nothing=False, number_options: dict[str, tuple[float, float, float]] | None = None)`. `number_options` maps a name to `(default, minimum, maximum)` and uses `go.AddOptionDouble` with `Rhino.Input.Custom.OptionDouble(value, minimum, maximum)`. Values are stored in the same sticky dict and returned in the same `values` dict as floats. Existing callers are unchanged.

- [ ] **Step 1: Implement.** Re-read the `OptionDouble` current value after each `GetResult.Option`, and re-create the options on every loop iteration as the list options are.
- [ ] **Step 2: Verify:** `uvx ruff check src/pocketknife/rhinoui.py`. In Rhino, the user's run of the existing `sandbox`/`commands` scripts still works; this is checked together with Task 7.
- [ ] **Step 3: Commit** `Support number options in get_objects_with_options`.

### Task 6: Rhino adapter

**Files:** Create `src/pocketknife/rhinocurves.py`. The spec said `rhinoutil.py`; a separate file keeps `rhinoutil` focused, and it is the builder's call.

**Interfaces:**
- Consumes: everything in `curvegraph`.
- Produces:
  - `class CleanResult(NamedTuple)`: `curves: list[rg.Curve]`, `sources: list[int]` (input index giving layer and attributes to each output curve), `unchanged: list[int]` (input indices to leave in place), `skipped: list[int]` (non-planar inputs), `removed: int` (overlapping stretches removed).
  - `clean_curves(curves: list[rg.Curve], keys: list[Hashable], tol: float, max_angle_deg: float) -> CleanResult`. `keys` gives the group of each input. The command passes `(layer_index, color_source, color, linetype_source, linetype_index, plot_weight_source, plot_weight)` for `PerLayer` and `0` for `All`. GH passes `0`.
- Steps inside `clean_curves`, per key:
  1. Skip non-planar curves (`curve.TryGetPlane(tol)`). Group the planar ones by plane: same normal (parallel within the angle tolerance) and origin distance within `tol`.
  2. Explode with `DuplicateSegments()` (or the curve itself when it has no segments). Classify each segment: `TryGetPolyline`/`IsLinear(tol)` → line, `TryGetArc(plane, tol)` → arc, else free. Convert to `Segment` in plane coordinates (`plane.ClosestParameter`). Free segments get tangents from `TangentAt` and stay as `rg.Curve` in a side list, indexed by segment position.
  3. Free-curve overlaps: for each pair involving a free segment whose bounding boxes intersect, use `Rhino.Geometry.Intersect.Intersection.CurveCurve(a, b, tol, tol)`. On overlap events, `Trim` the shorter curve (or the line) to drop the overlapping interval, and split it into the remaining pieces.
  4. `drop_slivers` → `remove_overlaps` → `build_chains` → `compact_chain`.
  5. Assemble: if all pieces are lines, build an `rg.PolylineCurve`; otherwise an `rg.PolyCurve` of `LineCurve`/`ArcCurve`/free pieces, mapped back to 3D with `plane.PointAt`. `MakeClosed(tol)` when the chain is closed.
  6. Unchanged: if a chain's pieces all come from one input curve, every input segment of it is used, none was trimmed, and the compacted segment count equals that curve's original segment count, put the index in `unchanged` instead of adding a new curve.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify:** `uvx ruff check src/pocketknife/rhinocurves.py`. The Rhino check happens with Task 7.
- [ ] **Step 3: Commit** `Add Rhino adapter for curve cleaning`.

### Task 7: Sandbox command and Grasshopper script

**Files:**
- Create: `sandbox/pkCleanCurves.py` (`#! python3`, bootstrap from `sandbox/README.md`, structure of `commands/pkMinBoundingRect.py`)
- Create: `grasshopper/pkCleanCurves.py` (structure of `grasshopper/pkInnerPoint.py`)
- Modify: `grasshopper/README.md` (new `pkCleanCurves` section, nickname `pkCleanCrv`)

**Interfaces:**
- Consumes: `get_objects_with_options` with `number_options={"MaxAngle": (15.0, 0.0, 90.0)}`, and `clean_curves`.
- Command behaviour:
  - Prompt `Select curves`, curve filter, options `Layers=PerLayer/All`, `MaxAngle`, `DeleteInput=Yes/No`, sticky key `pkCleanCurves`.
  - Add each new curve with the attributes (`Duplicate()`) of `objects[sources[i]]`. Delete the inputs that are not in `unchanged` or `skipped` when `DeleteInput=Yes`.
  - Select the new curves and the unchanged ones.
  - Print `pkCleanCurves: {N} curves in -> {M} curves out, {K} duplicates removed, {S} skipped (non-planar).` Wrap everything in one undo record (`doc.BeginUndoRecord("pkCleanCurves")` / `EndUndoRecord`).
- GH component: inputs `C` (Curve, list) and `A` (float, item, default 15); output `C` = new curves plus the unchanged inputs. Warning balloon when `skipped` is not empty. `Message` = `f"{A:g}°"`.

- [ ] **Step 1: Implement both scripts and the README section.**
- [ ] **Step 2: Verify:** `uvx ruff check . && uvx ruff format --check . && uv run --no-project --python 3.9 --with pytest pytest`, all green.
- [ ] **Step 3: Commit and push** `Add pkCleanCurves sandbox prototype and Grasshopper script`.
- [ ] **Step 4: Hand over to the user for the Rhino test.** The checklist: a Make2D of a box grid, a grid with duplicates, an outline with inner T lines, a hidden line on the same layer with a dashed object linetype, `Layers=All`, `DeleteInput=No`, a non-planar curve, undo, and the GH component on the same curves. Stop here until the user approves.

### Task 8: Promote to the plug-in (only after the user approves in Rhino)

**Files:**
- Move: `sandbox/pkCleanCurves.py` → `commands/pkCleanCurves.py` (bootstrap replaced by the guarded import of the other commands)
- Modify: `tools/build_project.py` (add `pkCleanCurves` to the command list and to the GH component table with nickname `pkCleanCrv`, following the `pkMinBoundingRect` entries)
- Modify: `tools/build_icons.py` (add the `pkCleanCurves` icon definition in the same style as the others; it writes the SVG and the light/dark PNGs; needs `pip install cairosvg shapely`)
- Create: `docs/commands/pkCleanCurves.md` (same format as `docs/commands/pkMinBoundingRect.md`)
- Modify: `README.md` command table, `CHANGELOG.md`

- [ ] **Step 1: Make the changes.**
- [ ] **Step 2: Verify:** ruff and pytest green; `python tools/build_icons.py` produces `icons/png/pkCleanCurves-*.png`.
- [ ] **Step 3: Commit and push** `Approve pkCleanCurves: move to commands and document it`. The user rebuilds the `.rhproj`/`.rhp` in Rhino as described in `project/README.md`.

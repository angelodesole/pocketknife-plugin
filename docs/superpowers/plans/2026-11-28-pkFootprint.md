# pkFootprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `pkFootprint` Rhino command and Grasshopper component that turn
the buildings of a masterplan into the closed union outline on a plane,
ready for laser cutting, with a `MinArea` filter.

**Architecture:** The Make2D engine (`HiddenLineDrawing`) in a parallel view
along the plane normal gives the visible scene-silhouette segments. The
existing `clean_curves` join (extended with a separate join tolerance and a
split of chains at the nodes they pass twice) turns them into simple loops. A new pure-Python module nests the loops and drops
the small ones.

**Tech Stack:** Rhino 8 RhinoCommon, CPython 3.9.10, pytest.

**Spec:** `docs/superpowers/specs/2026-11-28-pkFootprint-design.md`

## Global Constraints

- CPython 3.9.10: `from __future__ import annotations`, no `match`, no numpy.
- Google Python Style Guide, English names and docstrings, ruff clean
  (`uvx ruff check . && uvx ruff format --check .`).
- Pure modules (no `Rhino` import) are tested with
  `uv run --no-project --python 3.9 --with pytest pytest`; `rhino*.py`
  modules are only checked in Rhino.
- Never modify or delete the input objects. Never move a vertex by more than
  the model tolerance, except the snap of an endpoint onto its node (at most
  `GapTolerance`).
- pkCleanCurves behaviour must not change: every new parameter defaults to
  today's behaviour, and all existing tests pass unchanged.
- Rhino checks are run through the Rhino MCP (`run_python` with
  `sys.path.insert(0, r"C:\dev\pocketknife-plugin\src")` and the module purge
  from `sandbox/README.md`, or `_-RunPythonScript` on the sandbox file with
  sticky options preset). Fix RhinoCommon mismatches from the error text.

## Review Focus

- A loop whose test point lies on another loop (corner-to-corner touch):
  the nesting must not make one loop the parent of the other. Test:
  `test_nest_corner_touch_siblings` (Task 2).
- Thousands of loops: nesting must not be quadratic in point-in-polygon
  tests. Test: `test_nest_scales` (Task 2).
- A CPlane whose normal points down (-Z) or is tilted: same loops and areas
  as World XY for objects lying flat on it. Check: Task 4 step "CPlane".
- Block instances nested two levels deep with a non-uniform transform: the
  footprint lands where the blocks are drawn. Check: Task 4 step "blocks".
- Empty or unusable selection (only curves, or nothing visible): a message,
  nothing added, no exception. Check: Task 5 step "empty".

---

### Task 1: Split chains at touch points in `curvegraph`

**Files:**
- Modify: `src/pocketknife/curvegraph.py` (`_pair_ends`, `build_chains`)
- Test: `tests/test_curvegraph.py`

**Interfaces:**
- Produces: `build_chains(segments, tol, max_angle, split_touches: bool = False) -> list[Chain]`.
  With `split_touches=True`, every chain that passes the same node twice is
  split there: the part between the two visits becomes its own closed chain,
  repeatedly, until no chain repeats a node (a closed chain that only meets
  its own start/end node is not split). Output order: open chains, then
  closed chains, as today.

Approach: `_pair_ends` also returns the node id of every end (it already
computes them with `fuse_endpoints`). After walking a chain, list the node
at each joint (`n0, n1, ..., nk`) and split with a stack: push nodes; when a
node is already on the stack, pop the items since its first occurrence as a
closed chain. Pairing itself is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def square(x0, y0, size, ccw=True):
    pts = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    if not ccw:
        pts.reverse()
    return [line_segment(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]


def loops(chains):
    return sorted(sorted(i for i, _ in c.items) for c in chains)


def test_split_corner_touch_gives_two_loops():
    segments = square(-1, -1, 1) + square(0, 0, 1)
    chains = build_chains(segments, TOL, math.pi, split_touches=True)
    assert all(c.closed for c in chains)
    assert loops(chains) == [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_split_holes_touching_gives_three_loops():
    segments = (
        square(-5, -5, 10)
        + square(-1, -1, 1, ccw=False)
        + square(0, 0, 1, ccw=False)
    )
    chains = build_chains(segments, TOL, math.pi, split_touches=True)
    assert all(c.closed for c in chains)
    assert loops(chains) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]


def test_split_skew_corner_touch():
    c, s = math.cos(0.5), math.sin(0.5)

    def rot(p):
        return (c * p[0] - s * p[1], s * p[0] + c * p[1])

    b = [line_segment(rot(g.start), rot(g.end)) for g in square(0, 0, 1)]
    chains = build_chains(square(-1, -1, 1) + b, TOL, math.pi, split_touches=True)
    assert len(chains) == 2 and all(ch.closed for ch in chains)


def test_split_off_keeps_todays_result():
    segments = square(-1, -1, 1) + square(0, 0, 1)
    assert build_chains(segments, TOL, MAX_ANGLE) == build_chains(
        segments, TOL, MAX_ANGLE, split_touches=False
    )
    assert len(build_chains(segments, TOL, math.pi)) == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --no-project --python 3.9 --with pytest pytest tests/test_curvegraph.py -k split -v`
Expected: FAIL with `TypeError: build_chains() got an unexpected keyword argument 'split_touches'`.

- [ ] **Step 3: Implement `split_touches`** and update the `build_chains`
  docstring.

- [ ] **Step 4: Run the whole curvegraph suite**

Run: `uv run --no-project --python 3.9 --with pytest pytest tests/test_curvegraph.py -v`
Expected: all pass, the existing tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/pocketknife/curvegraph.py tests/test_curvegraph.py
git commit -m "Add split_touches option to build_chains"
```

---

### Task 2: Loop nesting and `MinArea` (pure Python)

**Files:**
- Create: `src/pocketknife/footprint.py`
- Test: `tests/test_footprint.py`

**Interfaces:**
- Produces:
  - `nest_loops(polygons: Sequence[Sequence[Point2]], areas: Sequence[float]) -> list[int]`:
    parent index per loop (`-1` for a top-level loop). The parent is the
    loop of smallest area that contains the loop's test point.
  - `loop_depths(parents: Sequence[int]) -> list[int]`: 0 for top level;
    even depth = island, odd = hole.
  - `keep_loops(parents: Sequence[int], areas: Sequence[float], min_area: float) -> list[int]`:
    sorted indices of the loops kept: a loop is dropped if its area is
    `< min_area` or any ancestor is dropped. `min_area <= 0` keeps all.
- `Point2` is `tuple[float, float]` (import it from `pocketknife.curvegraph`).

Test point of a loop: the midpoint of its longest edge, nudged by `1e-9 *`
the loop's bounding-box diagonal toward the polygon's interior side (left
for counter-clockwise, right for clockwise by the shoelace sign). Loops of a
union outline never cross and share at most isolated points, so this point
decides containment. Containment: even-odd ray casting against the candidate
polygon. Candidates: only loops with a larger area whose bounding box
contains the point (sort loops by area once; use a uniform grid or sorted
x-intervals over bounding boxes so the scan is not all-pairs).

- [ ] **Step 1: Write the failing tests**

```python
from pocketknife.footprint import keep_loops, loop_depths, nest_loops


def sq(x0, y0, size):
    return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]


def test_nest_disjoint():
    polys = [sq(0, 0, 1), sq(5, 0, 1)]
    assert nest_loops(polys, [1, 1]) == [-1, -1]


def test_nest_three_levels():
    polys = [sq(2, 2, 1), sq(0, 0, 10), sq(1, 1, 5)]
    parents = nest_loops(polys, [1, 100, 25])
    assert parents == [2, -1, 1]
    assert loop_depths(parents) == [2, 0, 1]


def test_nest_siblings():
    polys = [sq(0, 0, 10), sq(1, 1, 2), sq(5, 5, 2)]
    assert nest_loops(polys, [100, 4, 4]) == [-1, 0, 0]


def test_nest_corner_touch_siblings():
    polys = [sq(-1, -1, 1), sq(0, 0, 1)]
    assert nest_loops(polys, [1, 1]) == [-1, -1]


def test_keep_small_island_dropped():
    assert keep_loops([-1, -1], [100, 0.5], 1.0) == [0]


def test_keep_small_hole_takes_inner_island():
    # island 0 > hole 1 (small) > island 2
    assert keep_loops([-1, 0, 1], [100, 0.8, 0.1], 1.0) == [0]


def test_keep_big_island_small_hole():
    assert keep_loops([-1, 0], [100, 0.5], 1.0) == [0]


def test_keep_zero_and_exact():
    assert keep_loops([-1, 0], [100, 0.5], 0.0) == [0, 1]
    assert keep_loops([-1], [1.0], 1.0) == [0]


def test_nest_scales():
    import time

    polys, areas = [], []
    for i in range(60):
        for j in range(60):
            polys.append(sq(i * 3, j * 3, 2))
            areas.append(4.0)
    t = time.perf_counter()
    assert nest_loops(polys, areas) == [-1] * 3600
    assert time.perf_counter() - t < 2.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --no-project --python 3.9 --with pytest pytest tests/test_footprint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pocketknife.footprint'`.

- [ ] **Step 3: Implement the three functions in `src/pocketknife/footprint.py`**

Module docstring in the style of `curvegraph.py`; no Rhino import.

- [ ] **Step 4: Run the tests**

Run: `uv run --no-project --python 3.9 --with pytest pytest tests/test_footprint.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/pocketknife/footprint.py tests/test_footprint.py
git commit -m "Add loop nesting and MinArea filter for pkFootprint"
```

---

### Task 3: `clean_curves` options for the footprint

**Files:**
- Modify: `src/pocketknife/rhinocurves.py` (`clean_curves`)

**Interfaces:**
- Consumes: `build_chains(..., split_touches=...)` (Task 1).
- Produces:
  `clean_curves(curves, keys, tol, max_angle_deg, angle_tol=radians(1), *, join_tol: float | None = None, split_touches: bool = False) -> CleanResult`.
  `join_tol` (default `tol`) is passed to `build_chains` only; slivers,
  overlaps, compaction and assembly keep `tol`. `split_touches` is passed
  to `build_chains`.

- [ ] **Step 1: Implement the two keyword parameters**

Update the docstring. Keep the positional signature unchanged.

- [ ] **Step 2: Check pkCleanCurves is unchanged in Rhino**

Run the pkCleanCurves Make2D case (3x3 boxes + cylinder, Top view
`_-Make2D`, `_-RunPythonScript sandbox\pkCleanCurves.py`).
Expected: `25 curves in -> 6 curves out`, total length 271.416.

- [ ] **Step 3: Check the new options in Rhino**

With `run_python`, `tol = 0.01`: two squares touching at a corner as
`LineCurve`s, `clean_curves(..., 180.0, split_touches=True)` gives 2 closed
curves. A square with a 0.02 break in one edge: open without `join_tol`,
closed with `join_tol=0.03`; an extra 0.02 long edge piece in that square is
kept (not dropped as a sliver) with `join_tol=0.03`.

- [ ] **Step 4: Run the pure suite and ruff, then commit**

Run: `uv run --no-project --python 3.9 --with pytest pytest && uvx ruff check . && uvx ruff format --check .`
Expected: all pass, no ruff findings.

```bash
git add src/pocketknife/rhinocurves.py
git commit -m "Add join_tol and split_touches options to clean_curves"
```

---

### Task 4: Rhino side of the footprint

**Files:**
- Create: `src/pocketknife/rhinofootprint.py`

**Interfaces:**
- Consumes: `clean_curves` (Task 3), `nest_loops`, `loop_depths`,
  `keep_loops` (Task 2).
- Produces:
  - `collect_geometry(objects: Sequence) -> tuple[list, int]`: from
    `RhinoObject`s **or** bare `GeometryBase` (GH), a list of
    `(geometry, rg.Transform)` the engine accepts, and the number skipped.
    Breps, extrusions, meshes as they are; SubD via
    `ToBrep(rg.SubDToBrepOptions.Default)`; `InstanceObject` recursively
    through `InstanceDefinition.GetObjects()` multiplying `InstanceXform`
    (depth limit 32). Anything else counts as skipped.
  - `class FootprintResult(NamedTuple)`: `closed: list` (curves),
    `open: list` (curves), `regions: int` (kept islands), `holes: int`
    (kept holes), `dropped: int` (loops removed by `MinArea`),
    `error: str` (empty on success).
  - `footprint(items: list, plane: rg.Plane, tol: float, gap_tol: float, min_area: float) -> FootprintResult`.

Pipeline (spec, "Pipeline" steps 2-7), building on
`sandbox/spike_pkFootprint.py`:

1. HLD parameters and parallel viewport exactly as in the spike
   (`Rhino.DocObjects.ViewportInfo`), each item added with its transform.
2. Keep visible segments with `IsSceneSilhouette`; map back with the
   inverse of `WorldToHiddenLine`, project with `PlanarProjection(plane)`.
3. `clean_curves(segments, [0]*n, tol, 180.0, join_tol=gap_tol, split_touches=True)`;
   output `result.curves` plus `segments[i]` for `result.unchanged`, each
   lone curve replaced by an `ArcCurve` when `TryGetCircle(tol)` /
   `TryGetArc(plane, tol)` succeeds.
4. Closed curves: polygon via `ToPolyline(0, 0, 0, 0, 0, tol, 0, 0, True)`
   (or `TryGetPolyline` when already a polyline), area via
   `AreaMassProperties.Compute`; then `nest_loops` / `keep_loops` /
   `loop_depths`. Open curves bypass nesting and go to `open`.
5. `error`: "No supported objects." when `items` is empty; "Footprint
   computation failed." when `HiddenLineDrawing.Compute` returns None.

- [ ] **Step 1: Implement the module**

- [ ] **Step 2: Re-run the spike scenes**

The 11-object scene and the 500-object scene from the spike findings, with
`gap_tol = 3 * tol`, `min_area = 0`.
Expected: 11 objects -> 9 closed loops, 0 open, cylinders `ArcCurve`;
500 objects -> 0 open, sampled-point check against the true union with no
mismatch, total time under 2 s.

- [ ] **Step 3: Edge cases**

- Corner touch: two boxes touching at a corner give two loops; two
  courtyards touching at a corner inside one block give three loops.
- `min_area = 5` on the 11-object scene: nothing dropped except loops under 5.
- "CPlane": plane with normal -Z, and a plane tilted 30° about X:
  same loop count and areas as World XY for objects lying flat on it.
- "blocks": a block of two boxes, placed through a second block, with a
  non-uniform scale on the outer instance: outline lands on the drawn boxes.

- [ ] **Step 4: Commit**

```bash
git add src/pocketknife/rhinofootprint.py
git commit -m "Add Rhino side of pkFootprint"
```

---

### Task 5: Command prototype

**Files:**
- Create: `sandbox/pkFootprint.py`
- Delete: `sandbox/spike_pkFootprint.py`

**Interfaces:**
- Consumes: `collect_geometry`, `footprint`, `FootprintResult` (Task 4);
  `get_objects_with_options` (`rhinoui`).

Command per spec "Rhino command": options `Plane` (`World`, `CPlane`),
number options `MinArea (0.0, 0.0, 1e12)` and
`GapTolerance (3 * tol, tol, 1e6)`, sticky key `"pkFootprint"`. After the
prompt, if `values["GapTolerance"]` equals the `3 * tol` default, delete that
key from `sc.sticky["pkFootprint"]` so the default keeps following the
document tolerance. Pre-selection allowed; object filter: breps, extrusions,
meshes, SubDs, instance references. Curves added to the current layer
(default attributes) in one undo record; selection and messages exactly as
in the spec, with the counts from `FootprintResult` and `collect_geometry`.

- [ ] **Step 1: Write the prototype** (bootstrap from `sandbox/README.md`)

- [ ] **Step 2: Run it in Rhino on the 11-object scene**

Preset `sc.sticky["pkFootprint"]`, pre-select, `_-RunPythonScript`.
Expected: `pkFootprint: 11 objects -> 8 regions (9 curves, 1 holes), 0 small loops dropped.` Then `_Undo`: the
curves disappear, the objects are untouched.

- [ ] **Step 3: "empty"**

Pre-select only curves, run. Expected: `pkFootprint: No supported objects.`
and nothing added.

- [ ] **Step 4: Commit**

```bash
git add sandbox/pkFootprint.py
git rm sandbox/spike_pkFootprint.py
git commit -m "Add pkFootprint sandbox prototype"
```

---

### Task 6: Grasshopper component

**Files:**
- Create: `grasshopper/pkFootprint.py`
- Modify: `grasshopper/README.md` (new section after pkRebuildCurves)

**Interfaces:**
- Consumes: `collect_geometry`, `footprint` (Task 4),
  `rhinoutil.document_tolerance`.

Inputs and outputs exactly as in the spec table (`G`, `P`, `A`, `T` ->
`C`, `O`), structure as `grasshopper/pkCleanCurves.py`. Warnings for open
curves, skipped objects and `error`. `ghenv.Component.Message` =
`f"{plane_name} | {min_area:g}"`, with `plane_name` `"World"` when `P` is
None else `"Plane"`.

- [ ] **Step 1: Write the script and the README section**

- [ ] **Step 2: Run it in Rhino** by exec'ing the file with injected
  globals (as done for the other GH scripts) on the 11-object scene.
  Expected: `C` has 9 curves, `O` empty, no warnings.

- [ ] **Step 3: Commit**

```bash
git add grasshopper/pkFootprint.py grasshopper/README.md
git commit -m "Add pkFootprint Grasshopper script"
```

---

### Task 7: Status and checklist

**Files:**
- Modify: `CLAUDE.md` (status table, "What each command does", Rhino test
  checklists)

- [ ] **Step 1: Update CLAUDE.md**

pkFootprint row: prototype `sandbox/pkFootprint.py`, GH
`grasshopper/pkFootprint.py`, spec and plan paths, state "Awaiting the
Rhino test". Replace the "(planned)" description with the shipped behaviour
in two or three lines. Replace the spike checklist with the eight points
of the spec's Rhino checklist. Mention that `clean_curves` gained
`join_tol` and `split_touches`.

- [ ] **Step 2: Final checks**

Run: `uv run --no-project --python 3.9 --with pytest pytest && uvx ruff check . && uvx ruff format --check .`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Update status for pkFootprint"
```

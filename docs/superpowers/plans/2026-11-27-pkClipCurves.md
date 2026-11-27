# pkClipCurves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Rhino command and a Grasshopper component that clip curves with closed mask shapes (even-odd), keeping only the inside or only the outside pieces, dropping stretches on the mask boundary, without moving geometry.

**Architecture:** Pure-Python interval logic in `src/pocketknife/intervals.py`, tested with pytest. It turns a curve domain, split parameters and overlap intervals into pieces, merges neighbours with the same state and filters them. The Rhino-only `src/pocketknife/rhinoclip.py` extracts mask loops, checks coplanarity, projects, prefilters with bounding boxes, gets intersection events, classifies pieces with `Curve.Contains`, and trims. The sandbox command and the GH script are thin front ends.

**Tech Stack:** CPython 3.9.10 (Rhino 8), RhinoCommon, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-11-27-pkClipCurves-design.md`

## Global Constraints

- Python 3.9 syntax, Google Python Style Guide, English names and docstrings, ruff clean (`uvx ruff check .`, `uvx ruff format --check .`).
- `intervals.py` must not import Rhino.
- Even-odd rule over all mask loops. `Keep=Inside` is the default; `Keep=Outside` is the alternative.
- Pieces on the mask boundary are always dropped.
- Split only at intersection parameters. Drop pieces not longer than the tolerance. Never move geometry.
- In-plane curves keep their type. Off-plane curves that need cutting are converted with `ToNurbsCurve()` first. Curves kept or dropped whole are left untouched.
- Touches don't split: neighbouring pieces with the same state are merged.
- Prototype in `sandbox/`, run with `_RunPythonScript`. Promote to `commands/` only after the user approves it in Rhino (out of this plan).

## Review Focus

- **Endpoint on the boundary:** a curve that ends exactly on a mask edge yields a split at the domain end. That split must not create a zero-length piece. Test in Task 1.
- **Curve identical to a mask loop:** overlap over the whole domain makes the curve a boundary curve, so it is dropped in both modes. Test in Task 1.
- **Duplicate events:** a crossing at a mask vertex, or at the shared point of two loops, gives the same parameter twice. The two splits fuse into one. Test in Task 1.
- **Same object in both selections:** it counts as a mask only, so it is never clipped against itself. This is handled in Task 4.
- **Many masks:** with 5,000 curves and 500 masks, each curve meets only the masks whose box it touches. The bounding-box prefilter is in Task 3; the reviewer checks there is no all-pairs loop over `Intersection.CurveCurve`.

---

### Task 1: Pieces from splits and overlaps

**Files:** Create `src/pocketknife/intervals.py`, `tests/test_intervals.py`

**Interfaces:**
- Produces:
  - `INSIDE, OUTSIDE, BOUNDARY, DROP = "inside", "outside", "boundary", "drop"`
  - `class Piece(NamedTuple)`: `t0: float`, `t1: float`, `state: str`. On a closed curve, a piece spanning the seam has `t0 > t1`.
  - `split_domain(domain: tuple[float, float], splits: Sequence[float], overlaps: Sequence[tuple[float, float]], closed: bool, param_tol: float) -> list[Piece]`. Overlap ends count as splits too. Splits within `param_tol` fuse, and so do splits within `param_tol` of a domain end. Pieces inside an overlap get `BOUNDARY`; the others get `state=""`, to be classified later. On a closed curve with at least one split, the piece before the first split and the piece after the last split form one seam-spanning piece. A closed curve with no split gives a single piece over the whole domain. Pieces are returned in domain order.

- [ ] **Step 1: Write the failing tests**

```python
def test_one_crossing_gives_two_pieces():
    assert split_domain((0, 10), [4], [], False, 1e-9) == [Piece(0, 4, ""), Piece(4, 10, "")]

def test_overlap_in_the_middle():
    assert split_domain((0, 10), [], [(3, 6)], False, 1e-9) == [
        Piece(0, 3, ""), Piece(3, 6, BOUNDARY), Piece(6, 10, "")]

def test_overlap_at_the_end():
    assert split_domain((0, 10), [2], [(7, 10)], False, 1e-9) == [
        Piece(0, 2, ""), Piece(2, 7, ""), Piece(7, 10, BOUNDARY)]

def test_split_at_domain_end_adds_no_piece():
    assert split_domain((0, 10), [0, 10, 5], [], False, 1e-6) == [Piece(0, 5, ""), Piece(5, 10, "")]

def test_duplicate_splits_fuse():
    assert split_domain((0, 10), [4, 4 + 1e-9, 4], [], False, 1e-6) == [Piece(0, 4, ""), Piece(4, 10, "")]

def test_whole_domain_overlap_is_boundary():
    assert split_domain((0, 10), [], [(0, 10)], True, 1e-6) == [Piece(0, 10, BOUNDARY)]

def test_closed_curve_joins_across_seam():
    assert split_domain((0, 10), [2, 7], [], True, 1e-9) == [Piece(2, 7, ""), Piece(7, 2, "")]

def test_closed_curve_without_splits():
    assert split_domain((0, 10), [], [], True, 1e-9) == [Piece(0, 10, "")]
```

- [ ] **Step 2: Run and see them fail.** `uv run -q --no-project --python 3.9 --with pytest pytest tests/test_intervals.py`. Expected: ImportError.
- [ ] **Step 3: Implement.** Within `param_tol`, a fused split takes the first value in sorted order. A split within `param_tol` of a domain end snaps to that end and is then ignored. A piece is `BOUNDARY` if its midpoint lies inside an overlap interval. Overlaps may wrap the seam on closed curves (`lo > hi`), so the midpoint test handles wrap-around.
- [ ] **Step 4: Run the tests, see them pass, and run ruff.**
- [ ] **Step 5: Commit** `Add interval splitting for curve clipping`.

### Task 2: Even-odd, merge and keep

**Files:** Modify `src/pocketknife/intervals.py`, `tests/test_intervals.py`

**Interfaces:**
- Consumes: `Piece` and the state constants from Task 1.
- Produces:
  - `even_odd(count: int) -> str`: `INSIDE` if `count` is odd, else `OUTSIDE`.
  - `merge_same_state(pieces: list[Piece], closed: bool) -> list[Piece]`: merges consecutive pieces with the same `INSIDE`/`OUTSIDE` state. It never merges `BOUNDARY` or `DROP` pieces. On a closed curve it also merges the last piece with the first, which gives a seam-spanning piece. If everything merges into one piece on a closed curve, the result is `Piece(domain_min, domain_max, state)`; the function therefore also takes `domain: tuple[float, float]` as its third parameter.
  - `keep_pieces(pieces: list[Piece], keep_inside: bool) -> list[Piece]`: returns only the pieces in the kept state.
  - `covers_domain(pieces: list[Piece], domain: tuple[float, float]) -> bool`: True if there is a single piece spanning the whole domain. That means the curve is kept untouched.

- [ ] **Step 1: Write the failing tests**

```python
def test_even_odd():
    assert [even_odd(c) for c in range(4)] == [OUTSIDE, INSIDE, OUTSIDE, INSIDE]

def test_touch_merges_back():
    pieces = [Piece(0, 4, INSIDE), Piece(4, 10, INSIDE)]
    merged = merge_same_state(pieces, False, (0, 10))
    assert merged == [Piece(0, 10, INSIDE)] and covers_domain(merged, (0, 10))

def test_boundary_never_merged_nor_kept():
    pieces = [Piece(0, 3, INSIDE), Piece(3, 6, BOUNDARY), Piece(6, 10, INSIDE)]
    merged = merge_same_state(pieces, False, (0, 10))
    assert len(merged) == 3
    assert keep_pieces(merged, True) == [Piece(0, 3, INSIDE), Piece(6, 10, INSIDE)]
    assert keep_pieces(merged, False) == []

def test_closed_merge_across_seam():
    pieces = [Piece(2, 7, OUTSIDE), Piece(7, 9, INSIDE), Piece(9, 2, OUTSIDE)]
    assert merge_same_state(pieces, True, (0, 10)) == [Piece(7, 9, INSIDE), Piece(9, 7, OUTSIDE)]

def test_closed_all_same_state_is_whole_domain():
    pieces = [Piece(2, 7, INSIDE), Piece(7, 2, INSIDE)]
    assert merge_same_state(pieces, True, (0, 10)) == [Piece(0, 10, INSIDE)]

def test_drop_pieces_block_merge():
    pieces = [Piece(0, 4, INSIDE), Piece(4, 4.0001, DROP), Piece(4.0001, 10, INSIDE)]
    assert len(merge_same_state(pieces, False, (0, 10))) == 3
```

- [ ] **Step 2: Run and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite (`pytest`) and ruff, and see them pass.**
- [ ] **Step 5: Commit** `Add even-odd, merge and keep for curve clipping`.

### Task 3: Rhino adapter

**Files:** Create `src/pocketknife/rhinoclip.py`

**Interfaces:**
- Consumes: the whole `intervals` API.
- Produces:
  - `class MaskSet(NamedTuple)`: `loops: list[rg.Curve]` (on the plane), `boxes: list[tuple]` (plane-coordinate 2D boxes `(xmin, ymin, xmax, ymax)`), `plane: rg.Plane | None`, `ignored: int`, `error: str` (empty when OK).
  - `mask_set(geometries: Sequence, tol: float, angle_tol: float) -> MaskSet`. Closed curves are taken as they are. For hatches, all loops come from `Get3dCurves(True)` and `Get3dCurves(False)`. Open or non-planar curves and other types are counted in `ignored`. If no loop is found, `error = "No closed planar mask shape."`. If the loops are not coplanar, `error = "Mask shapes are not on one plane."`.
  - `class ClipResult(NamedTuple)`: `pieces: list[rg.Curve]`, `origins: list[int]`, `untouched: list[int]` (inputs kept whole), `removed: list[int]` (inputs dropped whole or replaced by pieces), `boundary: int` (on-boundary pieces dropped).
  - `clip_curves(curves: Sequence[rg.Curve], masks: MaskSet, tol: float, keep_inside: bool) -> ClipResult`.
- Steps inside `clip_curves`, per curve:
  1. In-plane test: both ends and `curve.PointAt(mid)` within `tol` of the plane, and `curve.IsPlanar(tol)` with a plane parallel to the mask plane, or `curve.IsLinear(tol)`. In-plane curves work on the curve itself. Otherwise `work = curve.ToNurbsCurve()`, `proj = work.Duplicate()` with `proj.Transform(Transform.PlanarProjection(plane))`. If the projected length is ≤ tol, classify the projected start point once and keep or drop the curve whole.
  2. Candidate masks: 2D box of `proj` in plane coordinates (from `GetBoundingBox(plane)`), expanded by `tol`, tested against `masks.boxes`. Use a sorted sweep on `xmin` computed once per call, not a per-curve scan of all masks when there are many.
  3. Events: `Intersection.CurveCurve(proj, loop, tol, tol)` per candidate. `e.IsOverlap` → `(e.OverlapA.Min, e.OverlapA.Max)`; otherwise → `e.ParameterA`.
  4. `param_tol = tol * domain.Length / max(proj.GetLength(), tol)`. Pieces = `split_domain(...)`.
  5. Each piece longer than `tol` (`proj.GetLength(Interval(t0, t1))`; for a seam piece, sum the two parts) that is not `BOUNDARY` is classified. Probe `proj.PointAt(mid)` (for a seam piece, the mid of the wrapped interval). Count the candidate loops whose 2D box contains the probe and whose `loop.Contains(probe, plane, tol)` is `PointContainment.Inside`. If any candidate returns `Coincident`, probe at 1/4 and 3/4 and take the majority of the non-coincident results; if still undecided → `BOUNDARY`. Pieces not longer than tol → `DROP`.
  6. `merge_same_state` → if `covers_domain` and that state is kept → `untouched`; if it covers the domain and is not kept → `removed` with no pieces. Otherwise `removed`, and for each kept piece `work.Trim(t0, t1)` (for a closed curve and `t0 > t1`, `Trim` crosses the seam), appended with its origin index.
  7. Count `BOUNDARY` pieces (after merge) into `boundary`.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify:** `uvx ruff check src/pocketknife/rhinoclip.py`. The Rhino check comes in Task 4.
- [ ] **Step 3: Commit** `Add Rhino adapter for curve clipping`.

### Task 4: Sandbox command and Grasshopper script

**Files:**
- Create: `sandbox/pkClipCurves.py`, `grasshopper/pkClipCurves.py`
- Modify: `grasshopper/README.md` (section `pkClipCurves`, nickname `pkClip`)

**Interfaces:**
- Consumes: `mask_set`, `clip_curves`, `get_objects_with_options`.
- Command:
  - First prompt `Select curves to clip` (curve filter, pre-selection allowed, no options).
  - Second prompt `Select mask shapes` (curves and hatches: `ObjectType.Curve | ObjectType.Hatch`) with options `Keep=Inside/Outside` and `DeleteMask=No/Yes`, sticky key `pkClipCurves`. Objects picked in both sets are removed from the curves to clip.
  - If `masks.error` is not empty: print `pkClipCurves: {error}` and return `Cancel` without changing anything.
  - Add the pieces with `objects[origin].Attributes.Duplicate()`. Delete `removed` inputs, and the mask objects with `DeleteMask=Yes`. Use one undo record (`BeginUndoRecord`/`EndUndoRecord`) and select the pieces plus the untouched inputs.
  - Print `pkClipCurves: {N} curves -> {M} pieces kept, {D} dropped ({B} on boundary).` Here `M` counts pieces plus untouched curves, and `D` counts `removed` inputs that produced no piece.
  - If `ignored > 0`, print `  {ignored} mask object(s) ignored (open or not planar).`
- GH: inputs `C` (Curve, list), `M` (GeometryBase, list), `O` (bool, default False); outputs `I` (pieces plus untouched curves, duplicated) and `X` (origin indices). Show `error` and `ignored` as warning balloons; `Message` = `"Outside"` or `"Inside"`.

- [ ] **Step 1: Implement both scripts and the README section.**
- [ ] **Step 2: Verify:** `uvx ruff check . && uvx ruff format --check . && uv run --no-project --python 3.9 --with pytest pytest`, all green.
- [ ] **Step 3: Commit and push** `Add pkClipCurves sandbox prototype and Grasshopper script`.
- [ ] **Step 4: Hand over for the Rhino test.** The checklist: a tangle cut by a rectangle with a circular hole (even-odd), `Keep=Outside`, curves along the mask edge (dropped), a curve touching the edge from inside (untouched), off-plane 3D curves, a hatch as mask, masks on two planes (error, nothing changed), and undo.

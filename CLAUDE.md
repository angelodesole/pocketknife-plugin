# Pocket Knife — notes for Claude

Free Rhino 8 plug-in (`pk*` commands + Grasshopper components) in pure
Python. Read `README.md` for the layout, `sandbox/README.md` for the
prototype workflow, `grasshopper/README.md` for components and
`project/README.md` for the build.

## The user

Computational designer and maker (architecture background), works in
Rhino and Grasshopper, some Python. Wants direct, concise answers.
Explanations in the chat language (Italian); code, names and docstrings in
English.

## Conventions

- **CPython 3.9.10** (the runtime embedded in Rhino 8). No `match`, use
  `from __future__ import annotations`. Google Python Style Guide, ruff clean.
- **Pure Python vs Rhino:** all decision logic lives in Rhino-free modules of
  `src/pocketknife/` and is tested with pytest in CI. Rhino-only modules
  (`rhino*.py`) only read geometry and build Rhino objects. No numpy.
- **Never lose geometry:** never delete an input unless its replacement was
  added; never move geometry beyond the tolerance.
- **Workflow for a new command:** brainstorm → design doc in
  `docs/superpowers/specs/` → plan in `docs/superpowers/plans/` → prototype
  in `sandbox/` run with `_RunPythonScript` → the user tests it in Rhino →
  promotion (below).
- Check and test:

  ```
  uvx ruff check . && uvx ruff format --check .
  uv run --no-project --python 3.9 --with pytest pytest
  ```

- The Rhino-only code has never run in CI. The first run in Rhino may show
  RhinoCommon / pythonnet API mismatches (overloads, out-parameters returned
  as tuples). Ask the user for the full error text and fix from it.

## Promoting an approved prototype

Do this only after the user approves the prototype in Rhino:

1. Move `sandbox/<name>.py` to `commands/<name>.py`. Replace the sandbox
   bootstrap with the guarded import used by the other commands (see
   `commands/pkMinBoundingRect.py`).
2. Add the command to `COMMANDS` in `tools/build_project.py`, and the
   Grasshopper component to its table (nickname, inputs and outputs as in
   `grasshopper/README.md`), following the existing entries.
3. Add the icon definition to `tools/build_icons.py`, in the same style, and
   run it (`pip install cairosvg shapely`).
4. Write `docs/commands/<name>.md` in the format of
   `docs/commands/pkMinBoundingRect.md`, then add a row to the README
   command table and an entry to `CHANGELOG.md`.
5. The user regenerates the project in Rhino (`tools/build_project.py`) and
   builds it (`tools/build_plugin.py`), as described in `project/README.md`.

## Status (branch `claude/curve-csv-commands-1s3xxh`)

| Command | Prototype | Design / plan | State |
|---|---|---|---|
| `pkCleanCurves` | `sandbox/pkCleanCurves.py`, GH `grasshopper/pkCleanCurves.py` | `specs/2026-11-25-pkCleanCurves-design.md`, `plans/2026-11-25-pkCleanCurves.md` | Rhino checks passed via MCP (2026-11-28); awaiting the user's approval |
| `pkClipCurves` | `sandbox/pkClipCurves.py`, GH `grasshopper/pkClipCurves.py` | `specs/2026-11-27-pkClipCurves-design.md`, `plans/2026-11-27-pkClipCurves.md` | Rhino checks passed via MCP (2026-11-28; Undo not checked); awaiting the user's approval |
| `pkRebuildCurves` | `sandbox/pkRebuildCurves.py`, GH `grasshopper/pkRebuildCurves.py` | `specs/2026-11-27-pkRebuildCurves-design.md`, `plans/2026-11-28-pkRebuildCurves.md` | Rhino checks passed via MCP (2026-11-28); awaiting the user's approval |
| `pkFootprint` | `sandbox/pkFootprint.py`, GH `grasshopper/pkFootprint.py` | `specs/2026-11-28-pkFootprint-design.md`, `plans/2026-11-28-pkFootprint.md` | Rhino checks passed via MCP (2026-11-28) |
| Read/Write CSV | — | — | Dropped (LunchBox is enough) |

### What each command does

- **pkCleanCurves**: messy planar networks such as Make2D output. Overlaps
  and duplicates are drawn once; pieces join at endpoints along the
  straightest continuation (`MaxAngle`, 15° by default); collinear lines
  and co-circular arcs merge. `Layers=PerLayer` groups by layer plus
  object-level attributes; `Layers=All` merges everything. Logic in
  `curvegraph.py`, Rhino side in `rhinocurves.py`.
- **pkClipCurves**: a clipping mask for curves. Even-odd rule over closed
  planar masks and hatches; `Keep=Inside/Outside`; stretches lying on the
  mask boundary are always dropped; touching the boundary does not split a
  curve. Logic in `intervals.py`, Rhino side in `rhinoclip.py`.
- **pkRebuildCurves**: faceted or over-dense curves from Revit, SketchUp or
  Blender become lines, true arcs and circles, and minimal NURBS. True
  corners are kept (`CornerAngle`, 45° by default: regular polygons with up
  to 8 sides stay polygons). Every vertex stays within `Tolerance`, and
  pieces that meet without a corner are tangent. Logic in `polyfit.py`,
  Rhino side in `rhinorebuild.py`.
- **pkFootprint**: the exact outline of the union of breps, meshes,
  SubDs and blocks on a plane (World by default, or CPlane), with real
  holes. `GapTolerance` (3x the model tolerance by default) joins the small
  gaps left by the Make2D engine; `MinArea` drops small islands and holes
  (a dropped hole takes its contents with it). Open curves are added too,
  selected and reported. Logic in `footprint.py`, Rhino side in
  `rhinofootprint.py`. It reuses the `pkCleanCurves` pipeline:
  `clean_curves` gained `join_tol` and `split_touches` (and `build_chains`
  `split_touches`), both off by default.

### Rhino test checklists

- **pkCleanCurves**:
  1. Make2D of a grid of boxes: long X and Y curves, no duplicates.
  2. An outline with inner T lines: a closed outline, inner lines kept separate.
  3. Hidden lines with an object linetype on the same layer: kept apart with `PerLayer`, merged with `All`.
  4. `DeleteInput=No`, a non-planar curve (skipped), and the `MaxAngle` value.
  5. Undo; the GH component on the same curves.
- **pkClipCurves**:
  1. A rectangle with a circular hole as mask (even-odd), then `Keep=Outside`.
  2. Curves along the mask edge: dropped.
  3. A curve inside that touches the edge: left untouched.
  4. Off-plane 3D curves.
  5. A hatch as mask.
  6. Masks on two planes: an error, nothing changed.
  7. Undo.
- **pkRebuildCurves**:
  1. A circle and a rounded rectangle from SketchUp.
  2. A dense Revit curve (also with a larger `Tolerance`, such as 0.01).
  3. An octagonal column: stays an octagon.
  4. An over-dense NURBS from FitCrv.
  5. A polycurve with a small kink: the kink stays.
  6. Undo.
- **pkFootprint**:
  1. A real masterplan: one closed curve per block, courtyards as holes,
     no inner lines.
  2. Buildings sharing walls and buildings 0.005 apart: one region each;
     2x tol apart: one region; touching at a corner: two loops sharing the
     point.
  3. A round tower: an exact circle (`ArcCurve`).
  4. `MinArea` on small courtyards and kiosks: they disappear, nothing
     else changes.
  5. Nested block instances, and `Plane=CPlane` with a rotated CPlane.
  6. An open curve (low `GapTolerance`): selected and reported.
  7. Undo; the GH component on the same objects.
  8. Timing on the biggest masterplan available.
  9. Run with a current layer that is not the first in the layer table: the
     curves go to the current layer.

### Known minor issues (deferred)

- pkClipCurves:
  - the probe box test has no tolerance at the outer edge of a mask box;
  - an overlap split by a seam is counted twice in "on boundary";
  - the mask index scan is not sublinear.
- pkRebuildCurves:
  - a 500-vertex free run at tolerance 0.001 takes about 7 s;
  - when the tangent-constrained arc fails, the arc/line join keeps a small kink.
- pkFootprint:
  - failed chains made only of segments <= GapTolerance vanish unreported, and
    a source shared by a good loop and a failed chain is output whole as open;
  - items rejected by `AddGeometry` are not counted as skipped;
  - "No supported objects." is also printed when no silhouettes come out;
  - mesh outlines come out as degree-1 NurbsCurve rather than PolylineCurve;
  - GH InstanceReferenceGeometry inputs are skipped;
  - a slit narrower than GapTolerance closes only when the facing walls share
    both end nodes (aligned buildings); staggered walls stay open and are
    reported;
  - 3840 objects take about 3.8 s (synthetic masterplan, 2026-11-28).

### Ideas not started

- None at the moment.


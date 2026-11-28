<img src="icons/svg/pocketknife-logo.svg" width="96" align="right" alt="">

# Pocket Knife

Free, open-source plug-in for **Rhino 8** that adds a set of `pk*` commands and
Grasshopper components. Written in pure Python 3 (CPython 3.9.10, the runtime
embedded in Rhino 8).

> Status: early development. Not yet published on Yak.

## Commands

| Command | Description | Grasshopper |
|---|---|---|
| [`pkLayerColorFromMaterial`](docs/commands/pkLayerColorFromMaterial.md) | Set layer color from the diffuse color of the layer material. | – |
| [`pkCopyToLayerCopy`](docs/commands/pkCopyToLayerCopy.md) | Copy or cut objects into a mirrored "Copy" layer structure. | – |
| [`pkInnerPoint`](docs/commands/pkInnerPoint.md) | Point always inside a geometry (pole of inaccessibility on XY). | ✓ |
| [`pkMinBoundingBox`](docs/commands/pkMinBoundingBox.md) | Minimum-volume oriented bounding box. | ✓ |
| [`pkMinBoundingRect`](docs/commands/pkMinBoundingRect.md) | Minimum-area bounding rectangle on XY. | ✓ |
| [`pkOrientToMinRect`](docs/commands/pkOrientToMinRect.md) | Rotate objects so their min rectangle aligns to X or Y. | ✓ |
| [`pkCleanCurves`](docs/commands/pkCleanCurves.md) | Clean messy curve networks (Make2D): no duplicates, straight joins. | ✓ |
| [`pkClipCurves`](docs/commands/pkClipCurves.md) | Clip curves with mask shapes, keeping the inside or the outside. | ✓ |
| [`pkRebuildCurves`](docs/commands/pkRebuildCurves.md) | Rebuild faceted curves into lines, true arcs and minimal NURBS. | ✓ |
| [`pkFootprint`](docs/commands/pkFootprint.md) | Closed union outline of many objects on a plane, with real holes. | ✓ |

## Install

Once published: Rhino 8 → `_PackageManager` → search **pocketknife** → Install.

## Build

See [project/README.md](project/README.md): `tools/build_project.py` (in
Rhino) generates the `.rhproj`, `tools/build_plugin.py` builds the `.rhp`,
`.gha` and `.yak`, `tools/release.py` publishes them
([docs/releasing.md](docs/releasing.md)).

## Platforms

- Windows: supported.
- macOS: expected to work (pure RhinoCommon), not yet tested.

## Repository layout

```
src/pocketknife/   shared library (geometry, layers, utilities)
sandbox/           prototypes to test with _RunPythonScript
commands/          approved Rhino commands (one file per command)
grasshopper/       Grasshopper component scripts (see grasshopper/README.md)
icons/svg/         icon sources
project/           Rhino Script Editor project (.rhproj) -> .rhp/.gha/.yak
tools/             icon, project and plug-in build scripts
tests/             pytest tests for Rhino-independent logic
docs/commands/     one page per command
```

## License

[MIT](LICENSE)

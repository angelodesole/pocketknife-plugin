# Pocket Knife

Free, open-source plug-in for **Rhino 8** that adds a set of `pk*` commands and
Grasshopper components. Written in pure Python 3 (CPython 3.9.10, the runtime
embedded in Rhino 8).

> Status: early development. Not yet published on Yak.

## Commands

| Command | Description | Grasshopper |
|---|---|---|
| `pkLayerColorFromMaterial` | Set layer color from the diffuse color of the layer material. | – |
| `pkCopyToLayerCopy` | Copy or cut objects into a mirrored "Copy" layer structure. | – |
| `pkInnerPoint` | Point always inside a geometry (pole of inaccessibility on XY). | ✓ |
| `pkMinBoundingBox` | Minimum-volume oriented bounding box. | ✓ |
| `pkMinBoundingRect` | Minimum-area bounding rectangle on XY. | ✓ |
| `pkOrientToMinRect` | Rotate objects so their min rectangle aligns to X or Y. | ✓ |

## Install

Once published: Rhino 8 → `_PackageManager` → search **pocketknife** → Install.

## Platforms

- Windows: supported.
- macOS: expected to work (pure RhinoCommon), not yet tested.

## Repository layout

```
src/pocketknife/   shared library (geometry, layers, utilities)
sandbox/           prototypes to test with _RunPythonScript
commands/          approved Rhino commands (one file per command)
grasshopper/       approved Grasshopper components
icons/svg/         icon sources
project/           Rhino Script Editor project (.rhproj) -> .rhp/.gha/.yak
tests/             pytest tests for Rhino-independent logic
docs/commands/     one page per command
```

## License

[MIT](LICENSE)

<img src="icons/svg/pocketknife-logo.svg" width="96" align="right" alt="">

# Pocket Knife

Free, open-source plug-in for **Rhino 8** that adds a set of `pk*` commands and
Grasshopper components. Written in pure Python 3 (CPython 3.9.10, the runtime
embedded in Rhino 8).

> Status: early development. Not yet published on Yak.
>
> Releases: [GitHub Releases](https://github.com/angelodesole/pocketknife-plugin/releases) · [Changelog](CHANGELOG.md)

## Commands

| Command | Description | Grasshopper |
|---|---|---|
| [`pkLayerColorFromMaterial`](docs/commands/pkLayerColorFromMaterial.md) | Set layer color from the diffuse color of the layer material. | – |
| [`pkCopyToLayerCopy`](docs/commands/pkCopyToLayerCopy.md) | Copy or cut objects into a mirrored "Copy" layer structure. | – |
| [`pkInnerPoint`](docs/commands/pkInnerPoint.md) | Point always inside a geometry (pole of inaccessibility on XY). | ✓ |
| [`pkMinBoundingBox`](docs/commands/pkMinBoundingBox.md) | Minimum-volume oriented bounding box. | ✓ |
| [`pkMinBoundingRect`](docs/commands/pkMinBoundingRect.md) | Minimum-area bounding rectangle on XY. | ✓ |
| [`pkOrientToMinRect`](docs/commands/pkOrientToMinRect.md) | Rotate objects so their min rectangle aligns to X or Y. | ✓ |

## Install

Once published: Rhino 8 → `_PackageManager` → search **pocketknife** → Install.

## Documentation

- Commands: one page per command in [`docs/commands/`](docs/commands/), linked from the table above.
- [Grasshopper components](grasshopper/README.md): inputs, outputs and setup.
- [Icons](icons/README.md): design rules and how to regenerate them.
- [Sandbox](sandbox/README.md): how to prototype and test a new command.
- [Releasing](docs/releasing.md): tag-triggered build, GitHub release and Yak publishing.

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
tests/             pytest tests for Rhino-independent logic
tools/             icon generator and release helper
docs/commands/     one page per command
docs/releasing.md  release process
.github/workflows/ CI and release workflows
```

## License

[MIT](LICENSE)

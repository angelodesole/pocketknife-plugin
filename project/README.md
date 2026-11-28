# Rhino 8 project

`pocketknife.rhproj` is the Rhino 8 Script Editor project that turns the
repository into the plug-in. It references, with paths relative to this folder:

| Project folder | Source |
|---|---|
| Commands | the ten scripts in `../commands/` (icons from `../icons/svg/`) |
| Components | the eight Script components of `pocketknife.gh` (made from `../grasshopper/`) |
| Libraries | the `pocketknife` package in `../src/pocketknife/` |

Both `pocketknife.rhproj` and `pocketknife.gh` are generated: edit the
sources and `tools/build_project.py`, not these files.

## Build

Requires Rhino 8.11 or later on Windows.

1. **Regenerate the project** (only when commands, components, their
   inputs/outputs or icons change). In Rhino 8:

   ```
   _-RunPythonScript "C:\dev\pocketknife-plugin\tools\build_project.py"
   ```

2. **Build** (Rhino does not need to be open):

   ```
   python tools\build_plugin.py
   ```

   Output:

   - `project/build/rh8/`: `PocketKnife.rhp`, `PocketKnife.rui`,
     `PocketKnife.Components.gha`
   - `dist/pocketknife-<version>-rh8_0-any.yak`: the Yak package, packed with
     `manifest.yml` (this folder) and the plug-in logo as icon.

The version comes from `pyproject.toml`.

## Test before publishing

Drag `project/build/rh8/PocketKnife.rhp` into Rhino, restart Rhino, then run
the `pk*` commands and check the **Pocket Knife** tab in Grasshopper. Remove it
afterwards in Options > Plug-ins before installing the published package.

## Publish

`tools/release.py` publishes the build (no build in CI); see
[docs/releasing.md](../docs/releasing.md) for the whole release.

```
python tools\release.py check
python tools\release.py test
python tools\release.py publish
```

`check` checks versions, `CHANGELOG.md`, the `.yak` and git and prints the
plan; `test` pushes the `.yak` to test.yak.rhino3d.com; `publish` tags
`vX.Y.Z`, creates the GitHub release (notes from `CHANGELOG.md`, the `.yak` and
a zip of `.rhp`/`.rui`/`.gha`) and pushes to Yak.

## Fixed ids

The project id and the component instance ids in `tools/build_project.py`
become the plug-in and component GUIDs. Never change them: installed copies
and saved Grasshopper definitions depend on them. Command ids are derived from
the command names, so renaming a command gives it a new id.

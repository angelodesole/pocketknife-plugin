# Rhino 8 project

`pocketknife.rhproj` is the Rhino 8 Script Editor project that turns the
repository into the plug-in. It references, with paths relative to this folder:

| Project folder | Source |
|---|---|
| Commands | the six scripts in `../commands/` (icons from `../icons/svg/`) |
| Components | the four Script components of `pocketknife.gh` (made from `../grasshopper/`) |
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

```
"C:\Program Files\Rhino 8\System\Yak.exe" login
"C:\Program Files\Rhino 8\System\Yak.exe" push dist\<package>.yak
```

## Fixed ids

The project id and the component instance ids in `tools/build_project.py`
become the plug-in and component GUIDs. Never change them: installed copies
and saved Grasshopper definitions depend on them. Command ids are derived from
the command names, so renaming a command gives it a new id.

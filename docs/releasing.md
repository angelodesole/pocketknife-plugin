# Releasing

Releases are built and published by [`.github/workflows/release.yml`](../.github/workflows/release.yml)
when a version tag is pushed.

| Trigger | Build | GitHub release | Yak |
|---|---|---|---|
| Tag `vX.Y.Z` | ✓ | ✓ | [yak.rhino3d.com](https://yak.rhino3d.com) |
| Tag `vX.Y.Z-beta.1` | ✓ | ✓ (pre-release) | yak.rhino3d.com, as pre-release |
| Manual run (Actions → Release → Run workflow) | ✓ | – | [test.yak.rhino3d.com](https://test.yak.rhino3d.com) (wiped every night) |

## Pipeline

1. **Check** (Ubuntu): `tools/release_info.py` checks that the tag matches the
   version in `pyproject.toml` and `src/pocketknife/__init__.py` and that
   `CHANGELOG.md` has a section for it, which becomes the release notes. Then
   ruff and pytest run as in CI.
2. **Build** (Windows): [`mcneel/setup-rhino3d`](https://github.com/mcneel/setup-rhino3d)
   installs Rhino 8, then `rhinocode project build project/pocketknife.rhproj`
   builds the `.rhp`, `.rui`, `.gha` and `.yak` with the tag version.
3. **GitHub release**: attaches the `.yak` and a `.zip` with `.rhp`/`.rui`/`.gha`
   for manual install (drag the `.rhp` into Rhino).
4. **Yak**: pushes the `.yak` with the standalone yak CLI.

## One-time setup

1. **Script Editor project.** In Rhino 8 (≥ 8.11) `_ScriptEditor` → File →
   New Project, save it as `project/pocketknife.rhproj`, add the commands from
   `commands/`, the shared library `src/pocketknife`, the Grasshopper file and
   the icons. Build it once from the editor (File → Publish Project) to check it.
2. **Rhino license for CI.** Set up
   core-hour billing on a Rhino account and create a token, as described in the
   [setup-rhino3d README](https://github.com/mcneel/setup-rhino3d#readme). Add repository secrets (Settings → Secrets and variables →
   Actions):
   - `RHINO_TOKEN`: the core-hour billing token.
   - `RHINO_EMAIL`: the e-mail of that Rhino account.
3. **Yak token.** On your computer run `yak login --ci` (yak is in
   `C:\Program Files\Rhino 8\System\Yak.exe`) and save the printed key as the
   secret `YAK_TOKEN`. The first push of a package name makes your account its
   owner.
4. **Approval gate (recommended).** Settings → Environments → New environment
   `yak` → Required reviewers: yourself. Every Yak publish then waits for your
   approval in the Actions run.

## Cutting a release

1. Set the version in `pyproject.toml` and `src/pocketknife/__init__.py`.
2. In `CHANGELOG.md` rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and
   add a new empty `## [Unreleased]` above it.
3. Commit on `main`, then tag and push:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. Approve the `yak` environment in the Actions run.

A pre-release tag (`v0.2.0-beta.1`) may keep the plain version (`0.2.0`) in the
files and use the `## [0.2.0]` changelog section.

Yak versions cannot be re-pushed, even after `yak yank`: to fix a bad release,
publish a new patch version.

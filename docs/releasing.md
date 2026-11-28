# Releasing

Pocket Knife is built on your PC (Rhino 8.11+ is needed, so there is no build
in CI). `tools/release.py` publishes what you built: it checks the files,
tags the commit, creates the GitHub release and pushes the package to
[Yak](https://yak.rhino3d.com).

## One-time setup

1. `gh auth login` (GitHub CLI).
2. `"C:\Program Files\Rhino 8\System\Yak.exe" login` (Rhino account). The
   first push of the `pocketknife` name makes your account its owner.

## Cutting a release

1. Set the version (`MAJOR.MINOR.PATCH`) in `pyproject.toml` and in
   `src/pocketknife/__init__.py`.
2. In `CHANGELOG.md` rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and
   add a new empty `## [Unreleased]` above it. That section becomes the
   release notes.
3. Commit and push to `main`.
4. Build (see [project/README.md](../project/README.md)): `tools/build_project.py`
   in Rhino if commands, components or icons changed, then
   `python tools/build_plugin.py`.
5. Check:

   ```
   python tools/release.py check
   ```

   It lists every problem at once: versions that differ, a missing or empty
   changelog section, a missing or wrong `.yak` in `dist/`, missing files in
   `project/build/rh8/`, not on a clean `main` equal to `origin/main`. It warns
   when the `.yak` is older than the last commit to the sources. When all is
   well it prints the notes and the plan.
6. Optional: try the package on the test server (wiped every night):

   ```
   python tools/release.py test
   ```

   Install it in Rhino with `_PackageManager` after adding
   `https://test.yak.rhino3d.com` as a source in Options > Package Manager,
   or with `Yak.exe install --source https://test.yak.rhino3d.com pocketknife`.
7. Publish:

   ```
   python tools/release.py publish
   ```

   Type the version to confirm. In order, it:
   1. creates the annotated tag `vX.Y.Z` on `HEAD` and pushes it;
   2. zips `PocketKnife.rhp`, `.rui` and `.gha` into
      `dist/pocketknife-X.Y.Z-rh8.zip`;
   3. creates the GitHub release with the notes, the `.yak` and the zip;
   4. pushes the `.yak` to Yak.

`--rhino <folder>` points to another Rhino 8 `System` folder.

## When something fails

Fix the cause and run `publish` again: a tag already on `HEAD` and assets
already on the release are skipped. If the tag exists on another commit,
publish a new version instead.

Yak is pushed last because a version cannot be pushed twice, even after
`yak yank`: to fix a bad release, publish a new patch version.

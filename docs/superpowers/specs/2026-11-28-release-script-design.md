# Release script — design

Date: 2026-11-28. Status: proposed.

## Intent

The plug-in is built on the user's PC (`tools/build_plugin.py`, Rhino 8.11+).
Publishing is manual today (`yak login`, `yak push`, nothing on GitHub).
Automate only what comes after the build: check that the version, the tag and
`CHANGELOG.md` agree, tag, create the GitHub release with notes and files, and
push to Yak, with a way to try the package on the Yak test server first.

## Goals

- One command, run on the PC that built the package.
- Nothing is published unless every check passes.
- A dry run by default; publishing needs an explicit flag and a typed
  confirmation.
- Safe to rerun after a failure: steps already done are skipped.

## Non-goals

- Building in CI, or any Rhino licence in CI.
- Bumping the version or editing `CHANGELOG.md` (the user does it by hand).
- Pre-release versions (`-beta.1`): the test server covers trying a package.
- A GitHub Actions workflow.

## Anti-goals

- Publishing a stale build (a `.yak` from an older commit or version).
- A half release that cannot be finished: Yak cannot re-push a version, so it
  comes last.

## Approaches

- **A. Local script (chosen by the user).** `tools/release.py` uses `gh` and
  `Yak.exe` with the logins already on the PC. No secrets on GitHub, one place
  to look when something fails.
- **B. Local script + Actions.** The script creates the tag and the release;
  a workflow on `release: published` pushes to Yak with a `YAK_TOKEN` secret.
  Gains an audit log and an approval gate, at the cost of a token to maintain,
  a second moving part and duplicated checks. Rejected.

## Design

### Files

- `tools/releasing.py`: pure, standard library only, no subprocess. All
  decision logic. Tested by `tests/test_releasing.py`.
- `tools/release.py`: the command line. Reads files, runs `git`, `gh` and
  `Yak.exe`, and calls `releasing.py` for every decision.
- `pyproject.toml`: pytest `pythonpath` gains `tools` (my call: keeps the
  release code out of the `pocketknife` package that ships in the plug-in).
- `docs/releasing.md`: how to cut a release. `project/README.md` Publish
  section points to it.

### Commands

```
python tools/release.py check            # default: all checks, prints the plan
python tools/release.py test             # checks, then push the .yak to test.yak.rhino3d.com
python tools/release.py publish          # checks, tag, GitHub release, Yak
```

`publish` asks to type the version (`0.1.0`) before doing anything.
`--rhino` overrides the Rhino 8 `System` folder, as in `build_plugin.py`.

### Checks (all in `releasing.py`)

1. Version is `MAJOR.MINOR.PATCH` and equal in `pyproject.toml` and
   `src/pocketknife/__init__.py`.
2. `CHANGELOG.md` has `## [X.Y.Z] - YYYY-MM-DD` with a non-empty body; the
   body (link reference lines dropped) is the release notes. A missing section
   says to rename `[Unreleased]`.
3. `dist/pocketknife-X.Y.Z-rh8_0-any.yak` exists; its `manifest.yml` has
   `name: pocketknife` and `version: X.Y.Z`, and the zip holds the `.rhp`,
   `.rui` and `.gha`.
4. `Yak.exe` exists and `gh` is logged in (`gh` skipped by `test`). (The
   first draft also checked `project/build/rh8/`; dropped after review because
   the zip now comes from the `.yak`.)
5. Git (skipped by `test`): on `main`, clean working tree, `HEAD` equal to
   `origin/main` after a fetch.
6. Staleness (warning, not an error): the `.yak` is older than the last commit
   touching `commands/`, `grasshopper/`, `src/`, `icons/` or `project/`.

### Publish steps, in order

Each step checks the current state first, so a rerun resumes:

1. Tag `vX.Y.Z` (annotated) on `HEAD` and push it. Exists on `HEAD`: skip.
   Exists elsewhere: stop with an error.
2. Zip `PocketKnife.rhp`, `.rui`, `.gha`, taken from the `.yak` (so GitHub
   and Yak get the same build), into `dist/pocketknife-X.Y.Z-rh8.zip`.
3. `gh release create vX.Y.Z --verify-tag --title "Pocket Knife X.Y.Z"
   --notes-file <notes>` with the `.yak` and the zip. Exists: upload only
   missing assets.
4. `Yak.exe push dist/<package>.yak` (last: it cannot be undone).

`test` runs only checks 1–4 and `Yak.exe push --source
https://test.yak.rhino3d.com` (the test server is wiped every night).

### Left to the builder

- Exact wording of messages; how `gh` and git outputs are parsed.
- Whether `yak login` is valid for the test server too is checked during the
  first `test` run with the user.

## Follow-up (out of scope)

- `project/manifest.yml`: description and keywords still list only six of the
  ten commands.

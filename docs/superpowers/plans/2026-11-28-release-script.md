# Release script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python tools/release.py check|test|publish` checks a locally built
release and publishes it to GitHub and Yak.

**Architecture:** `tools/releasing.py` holds every decision as pure functions
(strings, lists, numbers in; values out or `ReleaseError`). `tools/release.py`
reads files, runs `git`, `gh` and `Yak.exe`, and passes their output to
`releasing.py`.

**Tech Stack:** CPython 3.9 standard library, `gh`, `Yak.exe`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-28-release-script-design.md`

## Global Constraints

- Python 3.9, `from __future__ import annotations`, Google style docstrings,
  ruff clean, standard library only.
- Versions are `MAJOR.MINOR.PATCH` only; tag `vX.Y.Z`.
- Package `dist/pocketknife-X.Y.Z-rh8_0-any.yak`; zip
  `dist/pocketknife-X.Y.Z-rh8.zip`; files `PocketKnife.rhp`,
  `PocketKnife.rui`, `PocketKnife.Components.gha` in `project/build/rh8/`.
- Test server `https://test.yak.rhino3d.com`.
- Order in `publish`: tag, zip, GitHub release, Yak last.
- Never publish while running the plan: verify only with `check` and fakes.

## Review Focus

1. `CHANGELOG.md` with CRLF line endings or a UTF-8 BOM (Windows checkout):
   notes still extracted, without `\r`.
2. Only `## [Unreleased]` present: error names the rename to do.
3. `dist/` holding a `.yak` of an older version too: the right one is chosen
   by name, the other ignored.
4. Tag `vX.Y.Z` already on another commit: stop before any step.
5. Wrong confirmation typed in `publish`: nothing happens, exit code 1.

---

### Task 1: Pure checks in `tools/releasing.py`

**Files:**
- Create: `tools/releasing.py`, `tests/test_releasing.py`
- Modify: `pyproject.toml` (`[tool.pytest.ini_options] pythonpath = ["src", "tools"]`)

**Interfaces:**
- Produces:
  - `class ReleaseError(Exception)`
  - `PACKAGE_FILES: tuple[str, ...]` (the three file names)
  - `TEST_SOURCE = "https://test.yak.rhino3d.com"`
  - `parse_version(text: str) -> str`: `"v1.2.3"`/`"1.2.3"` → `"1.2.3"`, else `ReleaseError`
  - `check_versions(pyproject: str, init: str) -> str`: the shared version
  - `changelog_notes(text: str, version: str) -> str`
  - `yak_name(version: str) -> str`, `zip_name(version: str) -> str`
  - `check_yak(names: list[str], manifest: str, version: str) -> None`
  - `check_git(branch: str, dirty: bool, head: str, upstream: str) -> None`
  - `is_stale(package_mtime: float, last_source_commit: float) -> bool`
  - `tag_action(tag_commit: str | None, head: str) -> str`: `"create"` or `"skip"`
  - `missing_assets(existing: list[str] | None, wanted: list[str]) -> list[str]`

- [ ] **Step 1: Write the failing tests** in `tests/test_releasing.py`:
  - `parse_version`: `"v0.2.0"`→`"0.2.0"`, `"0.2.0"`→`"0.2.0"`; raises on `"0.2"`, `"v0.2.0-beta.1"`, `"x"`.
  - `check_versions`: equal → `"0.1.0"`; `0.1.0` vs `0.2.0` raises with both file names in the message; missing version raises.
  - `changelog_notes`: section between `## [0.2.0] - 2026-12-01` and the next `## ` returned stripped; last section stops before `[0.2.0]: https://…` link lines; CRLF and BOM input gives text without `\r`; only `[Unreleased]` raises with `"Unreleased"` in the message; heading without date raises; empty body raises.
  - `yak_name("0.1.0") == "pocketknife-0.1.0-rh8_0-any.yak"`, `zip_name("0.1.0") == "pocketknife-0.1.0-rh8.zip"`.
  - `check_yak`: passes with `manifest.yml`, icon and the three files and `name: pocketknife` / `version: 0.1.0`; raises on missing `.gha`, on `version: 0.0.9`, on another name.
  - `check_git`: passes for `main`, clean, head == upstream; raises naming each failing condition (branch, dirty, ahead/behind).
  - `is_stale(100.0, 200.0)` True, `is_stale(300.0, 200.0)` False.
  - `tag_action(None, "abc") == "create"`, `tag_action("abc", "abc") == "skip"`, `tag_action("def", "abc")` raises.
  - `missing_assets(None, ["a", "b"]) == ["a", "b"]`, `missing_assets(["a"], ["a", "b"]) == ["b"]`.

- [ ] **Step 2: Run, expect failure** — `uv run --no-project --python 3.9 --with pytest pytest tests/test_releasing.py` → `ModuleNotFoundError: releasing`.

- [ ] **Step 3: Implement `tools/releasing.py`.** Regexes as in `build_plugin.project_version`; `changelog_notes` normalises `\r\n` and strips `\ufeff` first, requires heading `^## \[X\.Y\.Z\] - \d{4}-\d{2}-\d{2}`, and drops `^\[[^\]]+\]:\s*\S+` lines. `check_yak` reads `name:` and `version:` lines with regexes (no YAML).

- [ ] **Step 4: Run, expect pass**, plus `uvx ruff check . && uvx ruff format --check .`.

- [ ] **Step 5: Commit** `Add pure release checks`.

### Task 2: Command line `tools/release.py`

**Files:**
- Create: `tools/release.py`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces: `main(argv: list[str] | None = None) -> int`; subcommands `check` (default), `test`, `publish`; `--rhino PATH` (default `C:\Program Files\Rhino 8\System`).

- [ ] **Step 1: Implement.** `ROOT` as in `build_plugin.py`. Helpers: `run(cmd, capture=False)` echoing like `build_plugin.run`; `gather(args) -> Release` (dataclass: version, notes, yak, zip paths) running checks 1–4 of the spec, collecting every `ReleaseError` and printing all before exiting 1; git check (`git fetch origin`, `git rev-parse --abbrev-ref HEAD`, `git status --porcelain`, `git rev-parse HEAD origin/main`) skipped for `test`; staleness warning from `git log -1 --format=%ct -- commands grasshopper src icons project` vs the `.yak` mtime.
  - `check`: prints version, notes, files and the publish plan (tag action, missing assets via `gh release view vX --json assets` — non-zero exit means no release).
  - `test`: `Yak.exe push --source TEST_SOURCE <yak>`.
  - `publish`: `input("Type the version to publish: ")` must equal the version, else print `Cancelled.` and return 1. Then tag (`git rev-list -n 1 vX` for the current tag commit; `git tag -a vX -m "Pocket Knife X"`, `git push origin vX`), zip with `zipfile` (ZIP_DEFLATED, flat names), `gh release create vX --verify-tag --title "Pocket Knife X" --notes-file <tmp>` with the assets or `gh release upload vX <missing>`, then `Yak.exe push <yak>`.
- [ ] **Step 2: Verify** in the worktree (no `dist/`, changelog only `[Unreleased]`): `python tools/release.py check` lists both errors (missing `[0.1.0]` section, missing `dist/pocketknife-0.1.0-rh8_0-any.yak`) and exits 1. Then, in a scratch copy where checks pass (temporary `dist/` with a fake `.yak`, changelog section), `publish` with `nope` typed prints `Cancelled.` and exits 1 before any git/gh/yak call.
- [ ] **Step 3: Ruff, pytest, commit** `Add tools/release.py`.

### Task 3: Docs

**Files:**
- Create: `docs/releasing.md`
- Modify: `project/README.md` (Publish section), `CHANGELOG.md` (`[Unreleased]` → Added), `README.md` if it lists the tools.

- [ ] **Step 1: Write `docs/releasing.md`:** one-time setup (`gh auth login`, `Yak.exe login`); cutting a release (bump both versions, rename `[Unreleased]` to `[X.Y.Z] - date` with a new empty `[Unreleased]`, commit and push to `main`, build, `check`, `test`, `publish`); rerun after a failure; Yak versions cannot be re-pushed, fix with a new patch.
- [ ] **Step 2: Replace the Publish section** of `project/README.md` with the three commands and a link to `docs/releasing.md`.
- [ ] **Step 3: Changelog entry**, ruff, pytest, commit `Document the release script`.

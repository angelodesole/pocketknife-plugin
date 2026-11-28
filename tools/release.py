"""Checks a locally built Pocket Knife release and publishes it.

Run after ``tools/build_plugin.py``, on the PC that built the package::

    python tools/release.py check     # checks, prints the plan (default)
    python tools/release.py test      # push the .yak to test.yak.rhino3d.com
    python tools/release.py publish   # tag, GitHub release, push to Yak

Needs ``git``, ``gh`` (logged in with ``gh auth login``) and Rhino 8's
``Yak.exe`` (logged in with ``Yak.exe login``). Decisions are made by
``tools/releasing.py``; see ``docs/releasing.md``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from releasing import (
    PACKAGE_FILES,
    TEST_SOURCE,
    ReleaseError,
    changelog_notes,
    check_git,
    check_versions,
    check_yak,
    is_stale,
    missing_assets,
    tag_action,
    yak_name,
    zip_name,
)

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "project" / "build" / "rh8"
DIST = ROOT / "dist"
RHINO_SYSTEM = Path(r"C:\Program Files\Rhino 8\System")
SOURCE_DIRS = ("commands", "grasshopper", "src", "icons", "project")


@dataclass
class Release:
    """A checked release: version, notes and the built files."""

    version: str
    notes: str
    yak: Path
    build: Path

    @property
    def tag(self) -> str:
        """The git tag, ``vX.Y.Z``."""
        return f"v{self.version}"

    @property
    def zip(self) -> Path:
        """The zip with the plug-in files, in ``dist/``."""
        return self.yak.parent / zip_name(self.version)


def output(command: list[str]) -> tuple[int, str]:
    """Runs a command quietly and returns its exit code and stripped stdout."""
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip()


def run(command: list[str]) -> None:
    """Runs a command, echoing it, and stops on failure."""
    print(">", " ".join(f'"{c}"' if " " in c else c for c in command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise ReleaseError(f"Failed with exit code {result.returncode}.")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_package(path: Path, version: str) -> None:
    if not path.exists():
        raise ReleaseError(
            f"Missing {path.relative_to(ROOT)}: run tools/build_plugin.py first."
        )
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        manifest = (
            package.read("manifest.yml").decode("utf-8")
            if "manifest.yml" in names
            else ""
        )
    check_yak(names, manifest, version)


def _git_state() -> None:
    if output(["git", "fetch", "--quiet", "origin"])[0] != 0:
        raise ReleaseError("git fetch origin failed.")
    branch = output(["git", "rev-parse", "--abbrev-ref", "HEAD"])[1]
    dirty = bool(output(["git", "status", "--porcelain"])[1])
    head = output(["git", "rev-parse", "HEAD"])[1]
    upstream = output(["git", "rev-parse", "origin/main"])[1]
    check_git(branch, dirty, head, upstream)


def gather(git: bool) -> Release:
    """Runs every check and returns the release.

    Args:
        git: Whether to check the git state (on ``main``, clean, pushed).

    Returns:
        The checked release.

    Raises:
        ReleaseError: Listing every check that failed.
    """
    problems = []

    def attempt(check):
        try:
            return check()
        except ReleaseError as error:
            problems.append(str(error))
            return None

    version = attempt(
        lambda: check_versions(
            _read(ROOT / "pyproject.toml"),
            _read(ROOT / "src" / "pocketknife" / "__init__.py"),
        )
    )
    notes = None
    yak = DIST / yak_name(version or "0.0.0")
    if version:
        notes = attempt(lambda: changelog_notes(_read(ROOT / "CHANGELOG.md"), version))
        attempt(lambda: _check_package(yak, version))
    missing = [name for name in PACKAGE_FILES if not (BUILD / name).exists()]
    if missing:
        problems.append(
            f"Missing in project/build/rh8: {', '.join(missing)}. "
            "Run tools/build_plugin.py first."
        )
    if git:
        attempt(_git_state)
    if problems:
        raise ReleaseError("\n".join(f"- {p}" for p in problems))

    code, last = output(["git", "log", "-1", "--format=%ct", "--", *SOURCE_DIRS])
    if code == 0 and last and is_stale(yak.stat().st_mtime, float(last)):
        print(
            "Warning: the .yak is older than the last commit to the sources. "
            "Rebuild with tools/build_plugin.py if they changed."
        )
    return Release(version=version, notes=notes, yak=yak, build=BUILD)


def plan(rel: Release) -> tuple[str, list[str]]:
    """Returns the tag action and the release assets still to upload."""
    code, commit = output(["git", "rev-list", "-n", "1", rel.tag])
    head = output(["git", "rev-parse", "HEAD"])[1]
    action = tag_action(commit if code == 0 and commit else None, head)
    code, names = output(
        ["gh", "release", "view", rel.tag, "--json", "assets", "-q", ".assets[].name"]
    )
    existing = names.splitlines() if code == 0 else None
    return action, missing_assets(existing, [rel.yak.name, rel.zip.name])


def write_zip(rel: Release) -> None:
    """Writes the zip with the ``.rhp``, ``.rui`` and ``.gha`` (flat)."""
    with zipfile.ZipFile(rel.zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in PACKAGE_FILES:
            archive.write(rel.build / name, name)
    print(f"Wrote {rel.zip.relative_to(ROOT)}")


def publish(rel: Release, yak_exe: Path) -> None:
    """Tags, creates or completes the GitHub release, then pushes to Yak."""
    action, missing = plan(rel)
    if action == "create":
        run(["git", "tag", "-a", rel.tag, "-m", f"Pocket Knife {rel.version}"])
    run(["git", "push", "origin", rel.tag])
    if rel.zip.name in missing or not rel.zip.exists():
        write_zip(rel)
    files = [str(DIST / name) for name in missing]
    if len(missing) == 2:
        with tempfile.TemporaryDirectory() as folder:
            notes = Path(folder) / "notes.md"
            notes.write_text(rel.notes + "\n", encoding="utf-8")
            run(
                [
                    "gh",
                    "release",
                    "create",
                    rel.tag,
                    "--verify-tag",
                    "--title",
                    f"Pocket Knife {rel.version}",
                    "--notes-file",
                    str(notes),
                    *files,
                ]
            )
    elif missing:
        run(["gh", "release", "upload", rel.tag, *files])
    else:
        print(f"GitHub release {rel.tag} already complete.")
    run([str(yak_exe), "push", str(rel.yak)])


def main(argv: list[str] | None = None) -> int:
    """Runs the command line interface and returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "action", nargs="?", default="check", choices=("check", "test", "publish")
    )
    parser.add_argument(
        "--rhino",
        type=Path,
        default=RHINO_SYSTEM,
        help=f"Rhino 8 System folder (default: {RHINO_SYSTEM})",
    )
    args = parser.parse_args(argv)
    yak_exe = args.rhino / "Yak.exe"
    try:
        rel = gather(git=args.action != "test")
        if args.action == "test":
            run([str(yak_exe), "push", "--source", TEST_SOURCE, str(rel.yak)])
            return 0
        action, missing = plan(rel)
        print(f"Version {rel.version}, tag {rel.tag}")
        print(f"Package {rel.yak.relative_to(ROOT)}")
        print(f"Release notes:\n\n{rel.notes}\n")
        if args.action == "check":
            print("Plan for publish:")
            print(f"  tag {rel.tag}: {action}")
            print(f"  GitHub assets to upload: {', '.join(missing) or 'none'}")
            print(f"  push {rel.yak.name} to Yak (cannot be undone)")
            return 0
        answer = input(f"Type {rel.version} to publish it to GitHub and Yak: ")
        if answer.strip() != rel.version:
            print("Cancelled.")
            return 1
        publish(rel, yak_exe)
        print(f"Published {rel.tag}.")
        return 0
    except ReleaseError as error:
        print(f"Release not ready:\n{error}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

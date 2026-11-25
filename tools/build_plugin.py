"""Builds the Pocket Knife plug-in: ``.rhp``, ``.gha`` and the Yak package.

1. ``RhinoCode.exe project build`` compiles ``project/pocketknife.rhproj``
   into ``project/build/rh8/`` (``PocketKnife.rhp``, ``.rui`` and
   ``PocketKnife.Components.gha``). Rhino does not need to be running.
2. The three files, the plug-in logo (``icon.png``) and ``project/manifest.yml``
   (with the version from ``pyproject.toml``) are packed by ``yak build`` into
   ``dist/pocketknife-<version>-rh8-any.yak``.

Run ``tools/build_project.py`` inside Rhino first if commands, components or
icons changed. Then, on Windows with Rhino 8.11 or later::

    python tools/build_plugin.py

Publish with ``yak push dist/<package>.yak`` (after ``yak login``).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "project" / "pocketknife.rhproj"
MANIFEST = ROOT / "project" / "manifest.yml"
BUILD_DIR = ROOT / "project" / "build"
DIST_DIR = ROOT / "dist"
ICON = ROOT / "icons" / "png" / "pocketknife-logo-128.png"
RHINO_SYSTEM = Path(r"C:\Program Files\Rhino 8\System")
PACKAGE_FILES = ("PocketKnife.rhp", "PocketKnife.rui", "PocketKnife.Components.gha")


def project_version() -> str:
    """Returns the version declared in ``pyproject.toml``."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if match is None:
        raise SystemExit("No version in pyproject.toml")
    return match.group(1)


def run(command: list[str], cwd: Path | None = None) -> None:
    """Runs a command, echoing it, and stops on failure.

    Args:
        command: Program and arguments.
        cwd: Working directory, or None for the current one.
    """
    print(">", " ".join(f'"{c}"' if " " in c else c for c in command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"Failed with exit code {result.returncode}")


def build_plugin(rhino_system: Path, version: str) -> Path:
    """Compiles the project with RhinoCode.

    Args:
        rhino_system: Rhino 8 ``System`` folder (contains ``RhinoCode.exe``).
        version: Build version, e.g. ``"0.1.0"``.

    Returns:
        The folder with the built ``.rhp``, ``.rui`` and ``.gha``.
    """
    run(
        [
            str(rhino_system / "RhinoCode.exe"),
            "project",
            "build",
            str(PROJECT),
            "--buildversion",
            version,
        ]
    )
    output = BUILD_DIR / "rh8"
    missing = [name for name in PACKAGE_FILES if not (output / name).exists()]
    if missing:
        raise SystemExit(f"Build output missing: {', '.join(missing)}")
    return output


def build_package(rhino_system: Path, output: Path, version: str) -> Path:
    """Packs the build output with the Pocket Knife manifest and icon.

    Args:
        rhino_system: Rhino 8 ``System`` folder (contains ``Yak.exe``).
        output: Folder with the built plug-in files.
        version: Package version written in ``manifest.yml``.

    Returns:
        Path of the ``.yak`` file in ``dist/``.
    """
    stage = BUILD_DIR / "yak"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    for name in PACKAGE_FILES:
        shutil.copy2(output / name, stage / name)
    shutil.copy2(ICON, stage / "icon.png")
    manifest = MANIFEST.read_text(encoding="utf-8").replace("{version}", version)
    (stage / "manifest.yml").write_text(manifest, encoding="utf-8")

    run([str(rhino_system / "Yak.exe"), "build", "--platform", "any"], cwd=stage)
    packages = sorted(stage.glob("*.yak"))
    if not packages:
        raise SystemExit("yak build produced no package")
    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / packages[-1].name
    shutil.copy2(packages[-1], target)
    return target


def main(argv: list[str] | None = None) -> None:
    """Parses the arguments and builds the plug-in and the package."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--rhino",
        type=Path,
        default=RHINO_SYSTEM,
        help=f"Rhino 8 System folder (default: {RHINO_SYSTEM})",
    )
    parser.add_argument(
        "--version", default=project_version(), help="Override the version."
    )
    args = parser.parse_args(argv)

    output = build_plugin(args.rhino, args.version)
    package = build_package(args.rhino, output, args.version)
    print(f"Plug-in: {output}")
    print(f"Package: {package}")


if __name__ == "__main__":
    main(sys.argv[1:])

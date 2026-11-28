"""Pure decision logic for ``tools/release.py``.

Every function takes strings, lists or numbers and returns a value or raises
:class:`ReleaseError`. Nothing here reads files or runs programs, so it is
tested with pytest in CI. Standard library only.
"""

from __future__ import annotations

import re

PACKAGE_NAME = "pocketknife"
PACKAGE_FILES = ("PocketKnife.rhp", "PocketKnife.rui", "PocketKnife.Components.gha")
TEST_SOURCE = "https://test.yak.rhino3d.com"

_VERSION = re.compile(r"^[vV]?(\d+\.\d+\.\d+)$")
_LINK_LINE = re.compile(r"(?m)^\[[^\]]+\]:\s*\S+.*$")


class ReleaseError(Exception):
    """The repository or the build is not ready for a release."""


def parse_version(text: str) -> str:
    """Returns the ``MAJOR.MINOR.PATCH`` version of a tag or version string.

    Args:
        text: ``"v1.2.3"`` or ``"1.2.3"``.

    Returns:
        The version without the ``v``, such as ``"1.2.3"``.

    Raises:
        ReleaseError: If the text is not a plain ``MAJOR.MINOR.PATCH`` version.
    """
    match = _VERSION.match(text.strip())
    if match is None:
        raise ReleaseError(f"{text!r} is not a version such as 1.2.3 or v1.2.3.")
    return match.group(1)


def _find(pattern: str, text: str, name: str) -> str:
    match = re.search(pattern, text, re.M)
    if match is None:
        raise ReleaseError(f"No version found in {name}.")
    return match.group(1)


def check_versions(pyproject: str, init: str) -> str:
    """Checks that ``pyproject.toml`` and the package declare the same version.

    Args:
        pyproject: Content of ``pyproject.toml``.
        init: Content of ``src/pocketknife/__init__.py``.

    Returns:
        The shared version.

    Raises:
        ReleaseError: If a version is missing, malformed or they differ.
    """
    project = _find(r'^version\s*=\s*"([^"]+)"', pyproject, "pyproject.toml")
    package = _find(
        r'^__version__\s*=\s*"([^"]+)"', init, "src/pocketknife/__init__.py"
    )
    if project != package:
        raise ReleaseError(
            f"pyproject.toml has {project} but src/pocketknife/__init__.py "
            f"has {package}."
        )
    return parse_version(project)


def changelog_notes(text: str, version: str) -> str:
    """Returns the body of the ``CHANGELOG.md`` section of a version.

    The section heading must be ``## [X.Y.Z] - YYYY-MM-DD``. Link reference
    lines (``[0.1.0]: https://...``) are dropped.

    Args:
        text: Content of ``CHANGELOG.md`` (Keep a Changelog format).
        version: ``MAJOR.MINOR.PATCH`` version.

    Returns:
        The section body, stripped, with LF line endings.

    Raises:
        ReleaseError: If the section is missing, has no date or is empty.
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    escaped = re.escape(version)
    heading = re.search(rf"(?m)^## \[{escaped}\][^\n]*$", text)
    if heading is None:
        raise ReleaseError(
            f"CHANGELOG.md has no '## [{version}] - YYYY-MM-DD' section. Rename "
            f"'## [Unreleased]' to it and add a new empty '## [Unreleased]' above."
        )
    if not re.match(rf"## \[{escaped}\] - \d{{4}}-\d{{2}}-\d{{2}}\s*$", heading[0]):
        raise ReleaseError(
            f"CHANGELOG.md heading {heading[0]!r} needs a date: "
            f"'## [{version}] - YYYY-MM-DD'."
        )
    following = re.compile(r"(?m)^## ").search(text, heading.end())
    end = following.start() if following else len(text)
    body = _LINK_LINE.sub("", text[heading.end() : end]).strip()
    if not body:
        raise ReleaseError(f"CHANGELOG.md section [{version}] is empty.")
    return body


def yak_name(version: str) -> str:
    """Returns the file name of the Yak package built by ``build_plugin.py``."""
    return f"{PACKAGE_NAME}-{version}-rh8_0-any.yak"


def zip_name(version: str) -> str:
    """Returns the file name of the zip with the plug-in files."""
    return f"{PACKAGE_NAME}-{version}-rh8.zip"


def check_yak(names: list[str], manifest: str, version: str) -> None:
    """Checks the content of a Yak package.

    Args:
        names: File names in the package (a zip).
        manifest: Content of its ``manifest.yml``.
        version: Expected version.

    Raises:
        ReleaseError: If files are missing or the manifest has another name or
            version.
    """
    missing = [n for n in ("manifest.yml", *PACKAGE_FILES) if n not in names]
    if missing:
        raise ReleaseError(f"The .yak package lacks {', '.join(missing)}.")
    name = re.search(r"(?m)^name:\s*(\S+)", manifest)
    found = re.search(r"(?m)^version:\s*(\S+)", manifest)
    if name is None or name.group(1) != PACKAGE_NAME:
        raise ReleaseError(f"The .yak manifest is not for {PACKAGE_NAME!r}.")
    if found is None or found.group(1) != version:
        actual = found.group(1) if found else "no version"
        raise ReleaseError(
            f"The .yak manifest has {actual}, expected {version}. Rebuild with "
            "tools/build_plugin.py."
        )


def check_git(branch: str, dirty: bool, head: str, upstream: str) -> None:
    """Checks that the release is made from a clean, pushed ``main``.

    Args:
        branch: Current branch name.
        dirty: Whether the working tree has uncommitted changes.
        head: Commit of ``HEAD``.
        upstream: Commit of ``origin/main``.

    Raises:
        ReleaseError: Naming every condition that fails.
    """
    problems = []
    if branch != "main":
        problems.append(f"the current branch is {branch!r}, not 'main'")
    if dirty:
        problems.append("the working tree has uncommitted changes")
    if head != upstream:
        problems.append("HEAD differs from origin/main (push or pull first)")
    if problems:
        raise ReleaseError("Git: " + "; ".join(problems) + ".")


def is_stale(package_mtime: float, last_source_commit: float) -> bool:
    """Returns whether the package was built before the last source commit."""
    return package_mtime < last_source_commit


def tag_action(tag_commit: str | None, head: str) -> str:
    """Decides what to do with the release tag.

    Args:
        tag_commit: Commit the tag points to, or None if it does not exist.
        head: Commit of ``HEAD``.

    Returns:
        ``"create"`` or ``"skip"`` (the tag is already on ``HEAD``).

    Raises:
        ReleaseError: If the tag exists on another commit.
    """
    if tag_commit is None:
        return "create"
    if tag_commit == head:
        return "skip"
    raise ReleaseError(
        f"The tag already exists on commit {tag_commit[:7]}, not on HEAD "
        f"({head[:7]}). Publish a new version instead."
    )


def missing_assets(existing: list[str] | None, wanted: list[str]) -> list[str]:
    """Returns the release assets still to upload.

    Args:
        existing: Asset names of the GitHub release, or None if there is no
            release yet.
        wanted: Asset names the release must have.

    Returns:
        The names in ``wanted`` that are not in ``existing``, in order.
    """
    if existing is None:
        return list(wanted)
    return [name for name in wanted if name not in existing]

"""Check a release tag against the repository and extract its release notes.

Used by `.github/workflows/release.yml`. Runs on any CPython >= 3.9 with the
standard library only.

Example:
    python tools/release_info.py v0.1.0 --notes release-notes.md
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# SemVer 2.0: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD].
SEMVER = re.compile(
    r"^(?P<core>\d+\.\d+\.\d+)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


class ReleaseError(Exception):
    """The tag does not match the repository state."""


def parse_tag(tag):
    """Returns the version of a release tag.

    Args:
        tag: Git tag or version, such as ``v0.1.0``, ``0.1.0`` or
            ``refs/tags/v0.2.0-beta.1``.

    Returns:
        A tuple ``(version, core, prerelease)``: the full SemVer string, its
        ``MAJOR.MINOR.PATCH`` part and whether it is a pre-release.

    Raises:
        ReleaseError: If the tag is not a SemVer version.
    """
    version = tag.rsplit("/", 1)[-1]
    if version[:1] in ("v", "V"):
        version = version[1:]
    match = SEMVER.match(version)
    if not match:
        raise ReleaseError(
            f"Tag {tag!r} is not a SemVer version such as v1.2.3 or v1.2.3-beta.1."
        )
    return version, match.group("core"), match.group("pre") is not None


def read_versions(root=ROOT):
    """Returns the versions declared in the repository.

    Args:
        root: Repository root.

    Returns:
        A dict ``{file name: version}`` for ``pyproject.toml`` and the
        ``pocketknife`` package.

    Raises:
        ReleaseError: If a version cannot be found.
    """
    sources = {
        "pyproject.toml": (
            root / "pyproject.toml",
            r'(?m)^version\s*=\s*"([^"]+)"',
        ),
        "src/pocketknife/__init__.py": (
            root / "src" / "pocketknife" / "__init__.py",
            r'(?m)^__version__\s*=\s*"([^"]+)"',
        ),
    }
    versions = {}
    for name, (path, pattern) in sources.items():
        match = re.search(pattern, path.read_text(encoding="utf-8"))
        if not match:
            raise ReleaseError(f"No version found in {name}.")
        versions[name] = match.group(1)
    return versions


def changelog_section(text, version, core):
    """Returns the body of the changelog section of a version.

    Looks for ``## [version]`` first, then for ``## [core]``.

    Args:
        text: Content of ``CHANGELOG.md`` (Keep a Changelog format).
        version: Full SemVer version.
        core: ``MAJOR.MINOR.PATCH`` part of the version.

    Returns:
        The section body without its heading, stripped.

    Raises:
        ReleaseError: If there is no section for the version or it is empty.
    """
    for wanted in dict.fromkeys((version, core)):
        heading = re.compile(rf"(?m)^## \[{re.escape(wanted)}\][^\n]*\n")
        match = heading.search(text)
        if not match:
            continue
        following = re.compile(r"(?m)^## ").search(text, match.end())
        end = following.start() if following else len(text)
        # Drop the link reference definitions at the bottom of the file.
        body = re.sub(r"(?m)^\[[^\]]+\]:\s*\S+\s*$", "", text[match.end() : end])
        body = body.strip()
        if not body:
            raise ReleaseError(f"CHANGELOG.md section [{wanted}] is empty.")
        return body
    raise ReleaseError(
        f"CHANGELOG.md has no '## [{version}]' section. Rename [Unreleased] "
        "to the version (with its date) before tagging."
    )


def check_release(tag, root=ROOT):
    """Checks a release tag and returns its version data and notes.

    Args:
        tag: Git tag or version.
        root: Repository root.

    Returns:
        A dict with ``version``, ``core``, ``prerelease`` and ``notes``.

    Raises:
        ReleaseError: If the declared versions differ from the tag or the
            changelog has no section for it.
    """
    version, core, prerelease = parse_tag(tag)
    wrong = {n: v for n, v in read_versions(root).items() if v not in (version, core)}
    if wrong:
        details = ", ".join(f"{n} has {v}" for n, v in wrong.items())
        raise ReleaseError(f"Tag is {version} but {details}.")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = changelog_section(changelog, version, core)
    return {"version": version, "core": core, "prerelease": prerelease, "notes": notes}


def main(argv=None):
    """Runs the command line interface.

    Args:
        argv: Arguments, without the program name. Defaults to ``sys.argv``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="release tag or version, e.g. v0.1.0")
    parser.add_argument("--notes", type=Path, help="write the release notes here")
    parser.add_argument(
        "--github-output", type=Path, help="append key=value lines (GITHUB_OUTPUT)"
    )
    args = parser.parse_args(argv)
    try:
        info = check_release(args.tag)
    except ReleaseError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    if args.notes:
        args.notes.write_text(info["notes"] + "\n", encoding="utf-8")
    lines = [
        f"version={info['version']}",
        f"prerelease={str(info['prerelease']).lower()}",
    ]
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for tools/release_info.py."""

import pytest

from release_info import ReleaseError, changelog_section, check_release, parse_tag

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0-beta.1] - 2026-12-01

### Added
- Beta thing.

## [0.1.0] - 2026-11-25

### Added
- First release.

[0.1.0]: https://example.com/v0.1.0
"""


def make_repo(tmp_path, version="0.1.0", changelog=CHANGELOG):
    (tmp_path / "src" / "pocketknife").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    (tmp_path / "src" / "pocketknife" / "__init__.py").write_text(
        f'__version__ = "{version}"\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.1.0", ("0.1.0", "0.1.0", False)),
        ("0.1.0", ("0.1.0", "0.1.0", False)),
        ("refs/tags/v1.2.3-beta.1", ("1.2.3-beta.1", "1.2.3", True)),
        ("v1.2.3+build.5", ("1.2.3+build.5", "1.2.3", False)),
    ],
)
def test_parse_tag(tag, expected):
    assert parse_tag(tag) == expected


@pytest.mark.parametrize("tag", ["v1.2", "release-1", "v1.2.3.4", "latest"])
def test_parse_tag_invalid(tag):
    with pytest.raises(ReleaseError):
        parse_tag(tag)


def test_changelog_section_stops_at_next_heading():
    body = changelog_section(CHANGELOG, "0.1.0", "0.1.0")
    assert body == "### Added\n- First release."


def test_changelog_section_prerelease_and_fallback():
    assert "Beta thing" in changelog_section(CHANGELOG, "0.2.0-beta.1", "0.2.0")
    # A pre-release without its own section uses the core version section.
    assert "First release" in changelog_section(CHANGELOG, "0.1.0-rc.1", "0.1.0")


def test_changelog_section_missing():
    with pytest.raises(ReleaseError, match="no '## \\[9.9.9\\]'"):
        changelog_section(CHANGELOG, "9.9.9", "9.9.9")


def test_check_release_ok(tmp_path):
    info = check_release("v0.1.0", make_repo(tmp_path))
    assert info["version"] == "0.1.0"
    assert info["prerelease"] is False
    assert info["notes"].startswith("### Added")


def test_check_release_prerelease_with_core_version(tmp_path):
    info = check_release("v0.2.0-beta.1", make_repo(tmp_path, version="0.2.0"))
    assert info["prerelease"] is True
    assert "Beta thing" in info["notes"]


def test_check_release_version_mismatch(tmp_path):
    with pytest.raises(ReleaseError, match="pyproject.toml has 0.1.0"):
        check_release("v0.3.0", make_repo(tmp_path))

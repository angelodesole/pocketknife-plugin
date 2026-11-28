"""Tests for tools/releasing.py."""

from __future__ import annotations

import pytest
from releasing import (
    ReleaseError,
    changelog_notes,
    check_git,
    check_tools,
    check_versions,
    check_yak,
    is_stale,
    missing_assets,
    parse_version,
    release_action,
    tag_action,
    yak_name,
    zip_name,
)

PYPROJECT = '[project]\nname = "pocketknife"\nversion = "{}"\n'
INIT = '"""Docstring."""\n\n__version__ = "{}"\n'

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-12-01

### Added
- Release script.

## [0.1.0] - 2026-11-28

### Added
- First release.

[0.2.0]: https://github.com/angelodesole/pocketknife-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/angelodesole/pocketknife-plugin/releases/tag/v0.1.0
"""

YAK_FILES = [
    "icon.png",
    "manifest.yml",
    "PocketKnife.Components.gha",
    "PocketKnife.rhp",
    "PocketKnife.rui",
]
MANIFEST = "---\nname: pocketknife\nversion: {}\nauthors:\n- Angelo\n"


@pytest.mark.parametrize("text", ["v0.2.0", "0.2.0", "V0.2.0"])
def test_parse_version_accepts_plain_and_v_prefixed(text):
    assert parse_version(text) == "0.2.0"


@pytest.mark.parametrize("text", ["0.2", "v0.2.0-beta.1", "x", "", "0.2.0+1"])
def test_parse_version_rejects_other_forms(text):
    with pytest.raises(ReleaseError):
        parse_version(text)


def test_check_versions_returns_shared_version():
    assert check_versions(PYPROJECT.format("0.1.0"), INIT.format("0.1.0")) == "0.1.0"


def test_check_versions_mismatch_names_both_files():
    with pytest.raises(ReleaseError) as error:
        check_versions(PYPROJECT.format("0.1.0"), INIT.format("0.2.0"))
    assert "pyproject.toml" in str(error.value)
    assert "__init__.py" in str(error.value)


def test_check_versions_missing_version():
    with pytest.raises(ReleaseError):
        check_versions('[project]\nname = "x"\n', INIT.format("0.1.0"))


def test_changelog_notes_middle_section():
    assert changelog_notes(CHANGELOG, "0.2.0") == "### Added\n- Release script."


def test_changelog_notes_last_section_drops_link_lines():
    assert changelog_notes(CHANGELOG, "0.1.0") == "### Added\n- First release."


def test_changelog_notes_crlf_and_bom():
    text = "\ufeff" + CHANGELOG.replace("\n", "\r\n")
    notes = changelog_notes(text, "0.2.0")
    assert notes == "### Added\n- Release script."
    assert "\r" not in notes


def test_changelog_notes_only_unreleased_says_rename():
    with pytest.raises(ReleaseError) as error:
        changelog_notes("# Changelog\n\n## [Unreleased]\n\n- Stuff.\n", "0.1.0")
    assert "Unreleased" in str(error.value)


def test_changelog_notes_heading_without_date():
    with pytest.raises(ReleaseError):
        changelog_notes("## [0.1.0]\n\n- Stuff.\n", "0.1.0")


def test_changelog_notes_empty_body():
    text = "## [0.1.0] - 2026-11-28\n\n## [0.0.1] - 2026-01-01\n- A\n"
    with pytest.raises(ReleaseError):
        changelog_notes(text, "0.1.0")


def test_changelog_notes_does_not_match_longer_version():
    with pytest.raises(ReleaseError):
        changelog_notes("## [0.1.0.1] - 2026-11-28\n\n- A\n", "0.1.0")


def test_package_names():
    assert yak_name("0.1.0") == "pocketknife-0.1.0-rh8_0-any.yak"
    assert zip_name("0.1.0") == "pocketknife-0.1.0-rh8.zip"


def test_check_yak_accepts_complete_package():
    check_yak(YAK_FILES, MANIFEST.format("0.1.0"), "0.1.0")


def test_check_yak_missing_gha():
    names = [n for n in YAK_FILES if not n.endswith(".gha")]
    with pytest.raises(ReleaseError) as error:
        check_yak(names, MANIFEST.format("0.1.0"), "0.1.0")
    assert "PocketKnife.Components.gha" in str(error.value)


def test_check_yak_wrong_version():
    with pytest.raises(ReleaseError) as error:
        check_yak(YAK_FILES, MANIFEST.format("0.0.9"), "0.1.0")
    assert "0.0.9" in str(error.value)


def test_check_yak_wrong_name():
    manifest = MANIFEST.format("0.1.0").replace("pocketknife", "other")
    with pytest.raises(ReleaseError):
        check_yak(YAK_FILES, manifest, "0.1.0")


def test_check_git_ok():
    check_git("main", False, "abc", "abc")


@pytest.mark.parametrize(
    "args, word",
    [
        (("dev", False, "abc", "abc"), "main"),
        (("main", True, "abc", "abc"), "uncommitted"),
        (("main", False, "abc", "def"), "origin/main"),
    ],
)
def test_check_git_reports_condition(args, word):
    with pytest.raises(ReleaseError) as error:
        check_git(*args)
    assert word in str(error.value)


def test_is_stale():
    assert is_stale(100.0, 200.0)
    assert not is_stale(300.0, 200.0)


def test_tag_action():
    assert tag_action(None, "abc") == "create"
    assert tag_action("abc", "abc") == "skip"
    with pytest.raises(ReleaseError):
        tag_action("def", "abc")


def test_missing_assets():
    assert missing_assets(None, ["a", "b"]) == ["a", "b"]
    assert missing_assets(["a"], ["a", "b"]) == ["b"]
    assert missing_assets(["a", "b"], ["a", "b"]) == []


def test_release_action_creates_when_no_release():
    assert release_action(None, ["a", "b"]) == ("create", ["a", "b"])


def test_release_action_uploads_to_empty_release():
    assert release_action([], ["a", "b"]) == ("upload", ["a", "b"])


def test_release_action_none_when_complete():
    assert release_action(["a", "b"], ["a", "b"]) == ("none", [])


def test_check_tools_ok():
    check_tools(yak_found=True, gh_logged_in=True)


def test_check_tools_reports_both():
    with pytest.raises(ReleaseError) as error:
        check_tools(yak_found=False, gh_logged_in=False)
    assert "Yak.exe" in str(error.value)
    assert "gh auth login" in str(error.value)

"""Tests for the confirmation gate of tools/release.py."""

from __future__ import annotations

import release
from releasing import ReleaseError


def _fake_release():
    return release.Release(
        version="0.1.0",
        notes="- Notes.",
        yak=release.DIST / "pocketknife-0.1.0-rh8_0-any.yak",
    )


def test_publish_wrong_confirmation_runs_nothing(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(release, "gather", lambda git, yak_exe: _fake_release())
    monkeypatch.setattr(release, "plan", lambda rel: ("create", "create", []))
    monkeypatch.setattr(release, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(release, "output", lambda *a, **k: calls.append(a))
    monkeypatch.setattr("builtins.input", lambda prompt="": "nope")
    assert release.main(["publish"]) == 1
    assert calls == []
    assert "Cancelled." in capsys.readouterr().out


def test_failed_checks_exit_one(monkeypatch, capsys):
    def fail(git, yak_exe):
        raise ReleaseError("CHANGELOG.md has no section.")

    monkeypatch.setattr(release, "gather", fail)
    assert release.main(["check"]) == 1
    assert "CHANGELOG.md has no section." in capsys.readouterr().out


def test_write_zip_takes_files_from_the_yak(tmp_path):
    import zipfile

    yak = tmp_path / "pocketknife-0.1.0-rh8_0-any.yak"
    with zipfile.ZipFile(yak, "w") as package:
        package.writestr("manifest.yml", "name: pocketknife\nversion: 0.1.0\n")
        package.writestr("icon.png", b"png")
        for name in release.PACKAGE_FILES:
            package.writestr(name, f"yak {name}")
    target = tmp_path / "out.zip"
    release.write_zip(yak, target)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == list(release.PACKAGE_FILES)
        assert archive.read("PocketKnife.rhp") == b"yak PocketKnife.rhp"

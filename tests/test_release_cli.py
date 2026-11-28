"""Tests for the confirmation gate of tools/release.py."""

from __future__ import annotations

import release
from releasing import ReleaseError


def _fake_release():
    return release.Release(
        version="0.1.0",
        notes="- Notes.",
        yak=release.DIST / "pocketknife-0.1.0-rh8_0-any.yak",
        build=release.BUILD,
    )


def test_publish_wrong_confirmation_runs_nothing(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(release, "gather", lambda git: _fake_release())
    monkeypatch.setattr(release, "plan", lambda rel: ("create", []))
    monkeypatch.setattr(release, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(release, "output", lambda *a, **k: calls.append(a))
    monkeypatch.setattr("builtins.input", lambda prompt="": "nope")
    assert release.main(["publish"]) == 1
    assert calls == []
    assert "Cancelled." in capsys.readouterr().out


def test_failed_checks_exit_one(monkeypatch, capsys):
    def fail(git):
        raise ReleaseError("CHANGELOG.md has no section.")

    monkeypatch.setattr(release, "gather", fail)
    assert release.main(["check"]) == 1
    assert "CHANGELOG.md has no section." in capsys.readouterr().out

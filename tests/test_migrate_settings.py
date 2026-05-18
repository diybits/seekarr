"""Tests for src/primary/utils/migrate_settings.py — nested-to-flat migration."""
import json
import pathlib
from unittest.mock import patch

import pytest

import src.primary.utils.migrate_settings as ms


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    """Redirect SETTINGS_DIR and SETTINGS_FILE to tmp_path."""
    monkeypatch.setattr(ms, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(ms, "SETTINGS_FILE", tmp_path / "huntarr.json")
    return tmp_path


def _write(settings_dir, data):
    (settings_dir / "huntarr.json").write_text(json.dumps(data))


def _read(settings_dir):
    return json.loads((settings_dir / "huntarr.json").read_text())


# ── no file ───────────────────────────────────────────────────────────────────

def test_no_file_is_no_op(settings_dir):
    ms.migrate_settings()  # must not raise


def test_no_file_does_not_create_file(settings_dir):
    ms.migrate_settings()
    assert not (settings_dir / "huntarr.json").exists()


# ── nothing to migrate ────────────────────────────────────────────────────────

def test_already_flat_file_is_unchanged(settings_dir):
    data = {"sonarr": {"hunt_missing_items": 10, "enabled": True}}
    _write(settings_dir, data)
    ms.migrate_settings()
    assert _read(settings_dir) == data


# ── huntarr section migration ─────────────────────────────────────────────────

def test_huntarr_section_keys_promoted_to_app_level(settings_dir):
    _write(settings_dir, {"sonarr": {"huntarr": {"hunt_missing_items": 5}}})
    ms.migrate_settings()
    result = _read(settings_dir)
    assert result["sonarr"]["hunt_missing_items"] == 5


def test_huntarr_section_removed_after_migration(settings_dir):
    _write(settings_dir, {"sonarr": {"huntarr": {"hunt_missing_items": 5}}})
    ms.migrate_settings()
    assert "huntarr" not in _read(settings_dir)["sonarr"]


def test_huntarr_existing_key_not_overwritten(settings_dir):
    _write(settings_dir, {
        "sonarr": {"hunt_missing_items": 99, "huntarr": {"hunt_missing_items": 1}}
    })
    ms.migrate_settings()
    assert _read(settings_dir)["sonarr"]["hunt_missing_items"] == 99


# ── advanced section migration ────────────────────────────────────────────────

def test_advanced_section_keys_promoted(settings_dir):
    _write(settings_dir, {"radarr": {"advanced": {"api_timeout": 30}}})
    ms.migrate_settings()
    assert _read(settings_dir)["radarr"]["api_timeout"] == 30


def test_advanced_section_removed_after_migration(settings_dir):
    _write(settings_dir, {"radarr": {"advanced": {"api_timeout": 30}}})
    ms.migrate_settings()
    assert "advanced" not in _read(settings_dir)["radarr"]


def test_advanced_existing_key_not_overwritten(settings_dir):
    _write(settings_dir, {
        "radarr": {"api_timeout": 10, "advanced": {"api_timeout": 60}}
    })
    ms.migrate_settings()
    assert _read(settings_dir)["radarr"]["api_timeout"] == 10


# ── multiple apps migrated in one pass ───────────────────────────────────────

def test_multiple_apps_migrated(settings_dir):
    _write(settings_dir, {
        "sonarr": {"huntarr": {"a": 1}},
        "radarr": {"advanced": {"b": 2}},
        "lidarr": {"c": 3},  # already flat — unchanged
    })
    ms.migrate_settings()
    result = _read(settings_dir)
    assert result["sonarr"]["a"] == 1
    assert result["radarr"]["b"] == 2
    assert result["lidarr"]["c"] == 3


# ── both sections in same app ─────────────────────────────────────────────────

def test_both_sections_migrated_for_same_app(settings_dir):
    _write(settings_dir, {
        "readarr": {
            "huntarr": {"x": 1},
            "advanced": {"y": 2},
        }
    })
    ms.migrate_settings()
    result = _read(settings_dir)["readarr"]
    assert result["x"] == 1
    assert result["y"] == 2
    assert "huntarr" not in result
    assert "advanced" not in result

"""Tests for src/primary/config.py — get_debug_mode and determine_hunt_mode."""
from unittest.mock import patch

import pytest

import src.primary.config as cfg


# ── get_debug_mode ────────────────────────────────────────────────────────────

def test_get_debug_mode_returns_true_when_enabled():
    with patch("src.primary.config.settings_manager.get_setting", return_value=True):
        assert cfg.get_debug_mode() is True


def test_get_debug_mode_returns_false_when_disabled():
    with patch("src.primary.config.settings_manager.get_setting", return_value=False):
        assert cfg.get_debug_mode() is False


def test_get_debug_mode_returns_false_on_exception():
    with patch("src.primary.config.settings_manager.get_setting", side_effect=Exception("boom")):
        assert cfg.get_debug_mode() is False


# ── determine_hunt_mode — sonarr ──────────────────────────────────────────────

def _mock_get_setting(values: dict):
    """Return a side_effect function that looks up (app, key, default) in values."""
    def _get(app, key, default=None):
        return values.get(key, default)
    return _get


def test_sonarr_both_returns_both():
    vals = {"hunt_missing_items": 10, "hunt_upgrade_items": 5}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("sonarr") == "both"


def test_sonarr_only_missing_returns_missing():
    vals = {"hunt_missing_items": 10, "hunt_upgrade_items": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("sonarr") == "missing"


def test_sonarr_only_upgrade_returns_upgrade():
    vals = {"hunt_missing_items": 0, "hunt_upgrade_items": 5}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("sonarr") == "upgrade"


def test_sonarr_both_zero_returns_disabled():
    vals = {"hunt_missing_items": 0, "hunt_upgrade_items": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("sonarr") == "disabled"


# ── determine_hunt_mode — radarr ──────────────────────────────────────────────

def test_radarr_both_returns_both():
    vals = {"hunt_missing_movies": 5, "hunt_upgrade_movies": 5}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("radarr") == "both"


def test_radarr_only_missing_returns_missing():
    vals = {"hunt_missing_movies": 3, "hunt_upgrade_movies": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("radarr") == "missing"


def test_radarr_only_upgrade_returns_upgrade():
    vals = {"hunt_missing_movies": 0, "hunt_upgrade_movies": 2}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("radarr") == "upgrade"


def test_radarr_both_zero_returns_disabled():
    vals = {"hunt_missing_movies": 0, "hunt_upgrade_movies": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("radarr") == "disabled"


# ── determine_hunt_mode — lidarr ──────────────────────────────────────────────

def test_lidarr_both_returns_both():
    vals = {"hunt_missing_items": 4, "hunt_upgrade_items": 4}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("lidarr") == "both"


def test_lidarr_only_missing_returns_missing():
    vals = {"hunt_missing_items": 2, "hunt_upgrade_items": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("lidarr") == "missing"


def test_lidarr_case_insensitive():
    vals = {"hunt_missing_items": 1, "hunt_upgrade_items": 0}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("Lidarr") == "missing"


# ── determine_hunt_mode — readarr ─────────────────────────────────────────────

def test_readarr_both_returns_both():
    vals = {"hunt_missing_books": 3, "hunt_upgrade_books": 3}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("readarr") == "both"


def test_readarr_only_upgrade_returns_upgrade():
    vals = {"hunt_missing_books": 0, "hunt_upgrade_books": 1}
    with patch("src.primary.config.settings_manager.get_setting", side_effect=_mock_get_setting(vals)):
        assert cfg.determine_hunt_mode("readarr") == "upgrade"


# ── determine_hunt_mode — unknown app ────────────────────────────────────────

def test_unknown_app_returns_disabled():
    assert cfg.determine_hunt_mode("unknownapp") == "disabled"


def test_whisparr_returns_disabled():
    # whisparr falls through to the else branch
    assert cfg.determine_hunt_mode("whisparr") == "disabled"

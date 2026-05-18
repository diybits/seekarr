"""Tests for src/primary/stats_manager.py — stats, hourly caps, reset."""
from unittest.mock import patch

import pytest

import src.primary.stats_manager as stats


# ── Default structures ────────────────────────────────────────────────────────

def test_default_stats_has_all_apps():
    result = stats.get_default_stats()
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr"]:
        assert app in result
        assert result[app] == {"hunted": 0, "upgraded": 0}


def test_default_hourly_caps_has_all_apps():
    result = stats.get_default_hourly_caps()
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        assert app in result
        assert result[app] == {"api_hits": 0}


# ── increment_stat ────────────────────────────────────────────────────────────

def test_increment_stat_hunted(config_dir):
    with patch.object(stats, "increment_hourly_cap", return_value=True):
        result = stats.increment_stat("sonarr", "hunted")
    assert result is True
    loaded = stats.load_stats()
    assert loaded["sonarr"]["hunted"] == 1


def test_increment_stat_upgraded(config_dir):
    with patch.object(stats, "increment_hourly_cap", return_value=True):
        stats.increment_stat("radarr", "upgraded")
    loaded = stats.load_stats()
    assert loaded["radarr"]["upgraded"] == 1


def test_increment_stat_accumulates(config_dir):
    with patch.object(stats, "increment_hourly_cap", return_value=True):
        stats.increment_stat("sonarr", "hunted")
        stats.increment_stat("sonarr", "hunted")
        stats.increment_stat("sonarr", "hunted")
    loaded = stats.load_stats()
    assert loaded["sonarr"]["hunted"] == 3


def test_increment_stat_invalid_app_returns_false(config_dir):
    result = stats.increment_stat("unknownapp", "hunted")
    assert result is False


def test_increment_stat_invalid_type_returns_false(config_dir):
    result = stats.increment_stat("sonarr", "invalidtype")
    assert result is False


def test_increment_stat_swaparr_skips_hourly_cap(config_dir):
    """swaparr should not call increment_hourly_cap."""
    with patch.object(stats, "increment_hourly_cap") as mock_cap:
        stats.increment_stat("swaparr", "hunted")
    mock_cap.assert_not_called()


# ── reset_stats ───────────────────────────────────────────────────────────────

def test_reset_all_stats(config_dir):
    with patch.object(stats, "increment_hourly_cap", return_value=True):
        stats.increment_stat("sonarr", "hunted")
        stats.increment_stat("radarr", "upgraded")

    stats.reset_stats()
    loaded = stats.load_stats()
    assert loaded["sonarr"]["hunted"] == 0
    assert loaded["radarr"]["upgraded"] == 0


def test_reset_specific_app_leaves_others_intact(config_dir):
    with patch.object(stats, "increment_hourly_cap", return_value=True):
        stats.increment_stat("sonarr", "hunted")
        stats.increment_stat("radarr", "hunted")

    stats.reset_stats("sonarr")
    loaded = stats.load_stats()
    assert loaded["sonarr"]["hunted"] == 0
    assert loaded["radarr"]["hunted"] == 1


def test_reset_stats_invalid_app_returns_false(config_dir):
    result = stats.reset_stats("unknownapp")
    assert result is False


# ── hourly cap ────────────────────────────────────────────────────────────────

def test_hourly_cap_not_exceeded_initially(config_dir):
    assert stats.check_hourly_cap_exceeded("sonarr") is False


def test_hourly_cap_exceeded_after_reaching_limit(config_dir):
    # Default hourly_cap from settings is 20; increment past it
    with patch("src.primary.settings_manager.load_settings", return_value={"hourly_cap": 3}):
        stats.increment_hourly_cap("sonarr", 3)
        exceeded = stats.check_hourly_cap_exceeded("sonarr")
    assert exceeded is True


def test_hourly_cap_not_exceeded_just_under_limit(config_dir):
    with patch("src.primary.settings_manager.load_settings", return_value={"hourly_cap": 5}):
        stats.increment_hourly_cap("sonarr", 4)
        exceeded = stats.check_hourly_cap_exceeded("sonarr")
    assert exceeded is False


def test_hourly_cap_invalid_app_returns_false(config_dir):
    result = stats.check_hourly_cap_exceeded("unknownapp")
    assert result is False


def test_reset_hourly_caps_clears_to_zero(config_dir):
    with patch("src.primary.settings_manager.load_settings", return_value={"hourly_cap": 100}):
        stats.increment_hourly_cap("sonarr", 10)
    stats.reset_hourly_caps()
    caps = stats.load_hourly_caps()
    assert caps["sonarr"]["api_hits"] == 0

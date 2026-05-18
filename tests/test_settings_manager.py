"""Tests for src/primary/settings_manager.py — load, save, cache, defaults."""
import json

import pytest

import src.primary.settings_manager as sm


# ── Default config loading ────────────────────────────────────────────────────

def test_load_default_settings_known_app_returns_dict(config_dir):
    defaults = sm.load_default_app_settings("sonarr")
    assert isinstance(defaults, dict)
    assert "sleep_duration" in defaults
    assert defaults["sleep_duration"] == 900


def test_load_default_settings_unknown_app_returns_empty(config_dir):
    result = sm.load_default_app_settings("unknownapp")
    assert result == {}


def test_load_default_settings_all_known_apps(config_dir):
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "general"]:
        result = sm.load_default_app_settings(app)
        assert isinstance(result, dict), f"Expected dict for {app}"


# ── save / load round-trip ────────────────────────────────────────────────────

def test_save_and_load_round_trip(config_dir):
    data = {"sleep_duration": 1234, "monitored_only": False}
    assert sm.save_settings("sonarr", data) is True
    loaded = sm.load_settings("sonarr", use_cache=False)
    assert loaded["sleep_duration"] == 1234
    assert loaded["monitored_only"] is False


def test_load_settings_creates_file_from_defaults_when_missing(config_dir):
    settings_file = config_dir / "sonarr.json"
    assert not settings_file.exists()
    result = sm.load_settings("sonarr", use_cache=False)
    assert settings_file.exists()
    assert "sleep_duration" in result


def test_missing_keys_are_filled_from_defaults(config_dir):
    # Write a partial config — only sleep_duration, missing everything else
    partial = {"sleep_duration": 500}
    (config_dir / "sonarr.json").write_text(json.dumps(partial))
    sm.settings_cache.clear()

    result = sm.load_settings("sonarr", use_cache=False)
    # sleep_duration preserved
    assert result["sleep_duration"] == 500
    # default keys back-filled
    assert "monitored_only" in result
    assert "hunt_missing_items" in result


def test_save_settings_unknown_app_returns_false(config_dir):
    assert sm.save_settings("unknownapp", {"foo": "bar"}) is False


def test_load_settings_corrupted_json_falls_back_to_defaults(config_dir):
    (config_dir / "sonarr.json").write_text("this is not json {{{{")
    sm.settings_cache.clear()
    result = sm.load_settings("sonarr", use_cache=False)
    assert isinstance(result, dict)
    assert "sleep_duration" in result
    assert result["sleep_duration"] == 900


# ── Cache behaviour ───────────────────────────────────────────────────────────

def test_load_settings_populates_cache(config_dir):
    sm.settings_cache.clear()
    sm.load_settings("sonarr")
    assert "sonarr" in sm.settings_cache


def test_clear_cache_specific_app(config_dir):
    sm.load_settings("sonarr")
    sm.load_settings("radarr")
    sm.clear_cache("sonarr")
    assert "sonarr" not in sm.settings_cache
    assert "radarr" in sm.settings_cache


def test_clear_cache_all(config_dir):
    sm.load_settings("sonarr")
    sm.load_settings("radarr")
    sm.clear_cache()
    assert sm.settings_cache == {}


# ── get_setting helper ────────────────────────────────────────────────────────

def test_get_setting_returns_value(config_dir):
    sm.save_settings("sonarr", {"sleep_duration": 600})
    assert sm.get_setting("sonarr", "sleep_duration") == 600


def test_get_setting_missing_key_returns_default(config_dir):
    sm.save_settings("sonarr", {})
    assert sm.get_setting("sonarr", "nonexistent_key", "fallback") == "fallback"


def test_get_setting_missing_key_default_none(config_dir):
    sm.save_settings("sonarr", {})
    assert sm.get_setting("sonarr", "nonexistent_key") is None

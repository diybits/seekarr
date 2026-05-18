"""Tests for src/primary/keys_manager.py — load_api_keys and get_api_keys."""
from unittest.mock import patch

import pytest

import src.primary.keys_manager as km


# ── load_api_keys ─────────────────────────────────────────────────────────────

def test_load_api_keys_delegates_to_settings_manager():
    settings = {"api_url": "http://sonarr:8989", "api_key": "abc123"}
    with patch("src.primary.settings_manager.load_settings", return_value=settings) as mock:
        result = km.load_api_keys("sonarr")
    mock.assert_called_once_with("sonarr")
    assert result == settings


def test_load_api_keys_returns_empty_dict_for_unconfigured_app():
    with patch("src.primary.settings_manager.load_settings", return_value={}):
        result = km.load_api_keys("sonarr")
    assert result == {}


# ── get_api_keys — flat settings model ───────────────────────────────────────

def test_get_api_keys_flat_returns_url_and_key():
    settings = {"api_url": "http://radarr:7878", "api_key": "xyz789"}
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("radarr")
    assert url == "http://radarr:7878"
    assert key == "xyz789"


def test_get_api_keys_flat_missing_values_returns_empty_strings():
    with patch("src.primary.settings_manager.load_settings", return_value={}):
        url, key = km.get_api_keys("radarr")
    assert url == ""
    assert key == ""


# ── get_api_keys — instances model ────────────────────────────────────────────

def test_get_api_keys_instances_returns_first_enabled():
    settings = {
        "instances": [
            {"enabled": True, "api_url": "http://sonarr:8989", "api_key": "key1"},
            {"enabled": True, "api_url": "http://sonarr2:8989", "api_key": "key2"},
        ]
    }
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("sonarr")
    assert url == "http://sonarr:8989"
    assert key == "key1"


def test_get_api_keys_instances_skips_disabled():
    settings = {
        "instances": [
            {"enabled": False, "api_url": "http://disabled:8989", "api_key": "old"},
            {"enabled": True,  "api_url": "http://active:8989",   "api_key": "new"},
        ]
    }
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("sonarr")
    assert url == "http://active:8989"
    assert key == "new"


def test_get_api_keys_all_instances_disabled_returns_empty():
    settings = {
        "instances": [
            {"enabled": False, "api_url": "http://sonarr:8989", "api_key": "key1"},
        ]
    }
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("sonarr")
    assert url == ""
    assert key == ""


def test_get_api_keys_empty_instances_falls_back_to_flat():
    settings = {"instances": [], "api_url": "http://flat:8989", "api_key": "flatkey"}
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("sonarr")
    assert url == "http://flat:8989"
    assert key == "flatkey"


def test_get_api_keys_instance_enabled_defaults_to_true():
    # Instance without explicit "enabled" key should be treated as enabled
    settings = {
        "instances": [
            {"api_url": "http://implicit:8989", "api_key": "implicit_key"},
        ]
    }
    with patch("src.primary.settings_manager.load_settings", return_value=settings):
        url, key = km.get_api_keys("sonarr")
    assert url == "http://implicit:8989"
    assert key == "implicit_key"

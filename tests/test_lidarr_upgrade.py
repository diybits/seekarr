"""Tests for src/primary/apps/lidarr/upgrade.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.lidarr.upgrade as lidarr_upgrade


SETTINGS = {
    "api_url": "http://lidarr:8686",
    "api_key": "abc123",
    "instance_name": "Lidarr",
    "monitored_only": True,
    "hunt_upgrade_items": 3,
}

_NO_STOP = lambda: False

_ALBUM = {
    "id": 10,
    "title": "Album One",
    "artist": {"artistName": "Artist One"},
    "quality": {"quality": {"name": "MP3"}},
}


def _patch(monkeypatch, *, eligible=None, search_cmd=99, is_proc=False):
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.load_settings", lambda *a: {})
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.add_processed_id", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_cutoff_unmet_albums", lambda *a, **k: eligible)
    monkeypatch.setattr("src.primary.apps.lidarr.api.search_albums", lambda *a, **k: search_cmd)


def test_returns_false_when_no_api_url(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_url": ""}
    assert lidarr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_returns_false_when_no_api_key(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_key": ""}
    assert lidarr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_returns_false_when_hunt_upgrade_zero(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "hunt_upgrade_items": 0}
    assert lidarr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, eligible=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.check_state_reset", reset)
    lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("lidarr")


def test_returns_false_when_eligible_none(monkeypatch):
    _patch(monkeypatch, eligible=None)
    assert lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_eligible_empty(monkeypatch):
    _patch(monkeypatch, eligible=[])
    assert lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_processed(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM], is_proc=True)
    assert lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_processes_album_and_returns_true(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.increment_stat", inc)
    result = lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("lidarr", "upgraded")


def test_adds_processed_id_before_search(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM])
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.add_processed_id", add_proc)
    lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("lidarr", "Lidarr", "10")


def test_logs_history_on_success(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.log_processed_media", log_media)
    lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("lidarr", "Artist One - Album One", 10, "Lidarr", "upgrade")


def test_search_failure_returns_false(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM], search_cmd=None)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.upgrade.increment_stat", inc)
    result = lidarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_stop_before_search_aborts(monkeypatch):
    _patch(monkeypatch, eligible=[_ALBUM])
    result = lidarr_upgrade.process_cutoff_upgrades(SETTINGS, lambda: True)
    assert result is False

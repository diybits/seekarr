"""Tests for src/primary/apps/lidarr/missing.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.lidarr.missing as lidarr_missing


SETTINGS = {
    "api_url": "http://lidarr:8686",
    "api_key": "abc123",
    "instance_name": "Lidarr",
    "monitored_only": True,
    "skip_future_releases": False,
    "hunt_missing_items": 3,
    "hunt_missing_mode": "album",
}

_NO_STOP = lambda: False

_ALBUM = {"id": 10, "title": "Album One", "artistId": 1, "artist": {"artistName": "Artist One"}}


def _patch(monkeypatch, *, missing=None, search_cmd=99, artist_cmd=None, is_proc=False,
           artist_data=None, albums_data=None):
    monkeypatch.setattr("src.primary.apps.lidarr.missing.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.lidarr.missing.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.missing.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.lidarr.missing.add_processed_id", MagicMock(return_value=True))
    monkeypatch.setattr("src.primary.apps.lidarr.missing.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.missing.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_missing_albums", lambda *a, **k: missing)
    monkeypatch.setattr("src.primary.apps.lidarr.api.search_albums", lambda *a, **k: search_cmd)
    monkeypatch.setattr("src.primary.apps.lidarr.api.search_artist",
                        lambda *a, **k: {"id": artist_cmd or 77})
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_artist_by_id",
                        lambda *a, **k: artist_data or {"artistName": "Artist One"})
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_albums",
                        lambda *a, **k: albums_data or {})


def test_returns_false_when_no_api_url(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_url": ""}
    assert lidarr_missing.process_missing_albums(s, _NO_STOP) is False


def test_returns_false_when_no_api_key(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_key": ""}
    assert lidarr_missing.process_missing_albums(s, _NO_STOP) is False


def test_returns_false_when_hunt_zero(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "hunt_missing_items": 0}
    assert lidarr_missing.process_missing_albums(s, _NO_STOP) is False


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, missing=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.missing.check_state_reset", reset)
    lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("lidarr")


def test_returns_false_when_api_returns_none(monkeypatch):
    _patch(monkeypatch, missing=None)
    assert lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP) is False


def test_returns_false_when_api_returns_empty(monkeypatch):
    _patch(monkeypatch, missing=[])
    assert lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_processed_album_mode(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM], is_proc=True)
    assert lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP) is False


def test_album_mode_processes_and_returns_true(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.missing.increment_stat", inc)
    result = lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("lidarr", "hunted")


def test_album_mode_adds_processed_id(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM])
    add_proc = MagicMock(return_value=True)
    monkeypatch.setattr("src.primary.apps.lidarr.missing.add_processed_id", add_proc)
    lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP)
    called_ids = [c.args[2] for c in add_proc.call_args_list]
    assert "10" in called_ids


def test_album_mode_logs_history(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.missing.log_processed_media", log_media)
    lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("lidarr", "Artist One - Album One", 10, "Lidarr", "missing")


def test_album_mode_search_failure_returns_false(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM], search_cmd=None)
    result = lidarr_missing.process_missing_albums(SETTINGS, _NO_STOP)
    assert result is False


def test_artist_mode_searches_by_artist(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.lidarr.missing.increment_stat", inc)
    s = {**SETTINGS, "hunt_missing_mode": "artist"}
    result = lidarr_missing.process_missing_albums(s, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("lidarr", "hunted")


def test_artist_mode_returns_false_when_all_processed(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM], is_proc=True)
    s = {**SETTINGS, "hunt_missing_mode": "artist"}
    assert lidarr_missing.process_missing_albums(s, _NO_STOP) is False


def test_stop_check_none_is_safe(monkeypatch):
    _patch(monkeypatch, missing=[_ALBUM])
    result = lidarr_missing.process_missing_albums(SETTINGS, None)
    assert result is True

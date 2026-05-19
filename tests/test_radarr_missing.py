"""Tests for src/primary/apps/radarr/missing.py"""
from unittest.mock import MagicMock, patch

import pytest

import src.primary.apps.radarr.missing as radarr_missing


SETTINGS = {
    "api_url": "http://radarr:7878",
    "api_key": "abc123",
    "instance_name": "Radarr",
    "monitored_only": True,
    "skip_future_releases": False,
    "hunt_missing_movies": 5,
    "release_type": "physical",
}

_NO_STOP = lambda: False


def _patch(monkeypatch, *, missing=None, search=True, is_proc=False):
    monkeypatch.setattr("src.primary.apps.radarr.missing.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.radarr.missing.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.radarr.missing.add_processed_id", MagicMock(return_value=True))
    monkeypatch.setattr("src.primary.apps.radarr.missing.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.radarr.missing.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.radarr.api.get_movies_with_missing", lambda *a, **k: missing)
    monkeypatch.setattr("src.primary.apps.radarr.api.movie_search", lambda *a, **k: search)


def test_returns_false_when_no_api_url(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_url": ""}
    assert radarr_missing.process_missing_movies(s, _NO_STOP) is False


def test_returns_false_when_no_api_key(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "api_key": ""}
    assert radarr_missing.process_missing_movies(s, _NO_STOP) is False


def test_returns_false_when_hunt_missing_zero(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "hunt_missing_movies": 0}
    assert radarr_missing.process_missing_movies(s, _NO_STOP) is False


def test_returns_false_when_stop_requested_immediately(monkeypatch):
    _patch(monkeypatch)
    assert radarr_missing.process_missing_movies(SETTINGS, lambda: True) is False


def test_returns_false_when_api_returns_none(monkeypatch):
    _patch(monkeypatch, missing=None)
    assert radarr_missing.process_missing_movies(SETTINGS, _NO_STOP) is False


def test_returns_false_when_api_returns_empty(monkeypatch):
    _patch(monkeypatch, missing=[])
    assert radarr_missing.process_missing_movies(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_already_processed(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Movie", "year": 2020}], is_proc=True)
    assert radarr_missing.process_missing_movies(SETTINGS, _NO_STOP) is False


def test_processes_movie_and_returns_true(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Movie", "year": 2020}], search=True)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.missing.increment_stat", inc)
    result = radarr_missing.process_missing_movies(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("radarr", "hunted")


def test_adds_processed_id_after_successful_search(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 42, "title": "Movie", "year": 2021}], search=True)
    add_proc = MagicMock(return_value=True)
    monkeypatch.setattr("src.primary.apps.radarr.missing.add_processed_id", add_proc)
    radarr_missing.process_missing_movies(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("radarr", "Radarr", "42")


def test_logs_history_after_successful_search(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 7, "title": "Film", "year": 2022}], search=True)
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.missing.log_processed_media", log_media)
    radarr_missing.process_missing_movies(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("radarr", "Film (2022)", 7, "Radarr", "missing")


def test_search_failure_does_not_increment_stat(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Movie", "year": 2020}], search=False)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.missing.increment_stat", inc)
    result = radarr_missing.process_missing_movies(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_stop_mid_loop_returns_false_when_nothing_processed(monkeypatch):
    calls = [False, False, True]
    stop = iter(calls)
    _patch(monkeypatch, missing=[{"id": 1, "title": "Movie", "year": 2020}])
    monkeypatch.setattr("src.primary.apps.radarr.missing.is_processed", lambda *a: False)
    monkeypatch.setattr("src.primary.apps.radarr.api.movie_search", lambda *a, **k: False)
    result = radarr_missing.process_missing_movies(SETTINGS, lambda: next(stop, True))
    assert result is False


def test_future_releases_filtered_when_skip_enabled(monkeypatch):
    _patch(monkeypatch)
    future_movie = {"id": 1, "title": "Upcoming", "year": 2099, "physicalRelease": "2099-01-01T00:00:00Z"}
    monkeypatch.setattr("src.primary.apps.radarr.api.get_movies_with_missing", lambda *a, **k: [future_movie])
    s = {**SETTINGS, "skip_future_releases": True}
    result = radarr_missing.process_missing_movies(s, _NO_STOP)
    assert result is False


def test_digital_release_field_used_when_configured(monkeypatch):
    _patch(monkeypatch)
    past_digital = {"id": 2, "title": "Past Digital", "year": 2020, "digitalRelease": "2020-01-01T00:00:00Z"}
    monkeypatch.setattr("src.primary.apps.radarr.api.get_movies_with_missing", lambda *a, **k: [past_digital])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.missing.increment_stat", inc)
    s = {**SETTINGS, "skip_future_releases": True, "release_type": "digital"}
    result = radarr_missing.process_missing_movies(s, _NO_STOP)
    assert result is True
    inc.assert_called_once()

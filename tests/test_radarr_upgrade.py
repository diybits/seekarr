"""Tests for src/primary/apps/radarr/upgrade.py"""
from unittest.mock import MagicMock, patch

import pytest

import src.primary.apps.radarr.upgrade as radarr_upgrade


SETTINGS = {
    "api_url": "http://radarr:7878",
    "api_key": "abc123",
    "instance_name": "Radarr",
    "monitored_only": True,
    "hunt_upgrade_movies": 5,
}

_NO_STOP = lambda: False


def _patch(monkeypatch, *, eligible=None, search=True, is_proc=False):
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.add_processed_id", MagicMock(return_value=True))
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.radarr.api.get_cutoff_unmet_movies", lambda *a, **k: eligible)
    monkeypatch.setattr("src.primary.apps.radarr.api.movie_search", lambda *a, **k: search)


def test_returns_false_when_eligible_is_none(monkeypatch):
    _patch(monkeypatch, eligible=None)
    assert radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_eligible_is_empty(monkeypatch):
    _patch(monkeypatch, eligible=[])
    assert radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_already_processed(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 1, "title": "Movie", "year": 2020}], is_proc=True)
    assert radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_processes_movie_and_returns_true(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 1, "title": "Movie", "year": 2020}], search=True)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.increment_stat", inc)
    result = radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("radarr", "upgraded")


def test_adds_processed_id_on_success(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 99, "title": "Film", "year": 2019}], search=True)
    add_proc = MagicMock(return_value=True)
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.add_processed_id", add_proc)
    radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("radarr", "Radarr", "99")


def test_logs_history_on_success(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 5, "title": "Flick", "year": 2018}], search=True)
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.log_processed_media", log_media)
    radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("radarr", "Flick (2018)", 5, "Radarr", "upgrade")


def test_search_failure_returns_false(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 1, "title": "Movie", "year": 2020}], search=False)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.increment_stat", inc)
    result = radarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_stop_at_loop_start_aborts(monkeypatch):
    movie = {"id": 1, "title": "Movie", "year": 2020}
    _patch(monkeypatch, eligible=[movie])
    result = radarr_upgrade.process_cutoff_upgrades(SETTINGS, lambda: True)
    assert result is False


def test_instance_name_falls_back_to_name_key(monkeypatch):
    _patch(monkeypatch, eligible=[{"id": 1, "title": "Movie", "year": 2020}], search=True)
    add_proc = MagicMock(return_value=True)
    monkeypatch.setattr("src.primary.apps.radarr.upgrade.add_processed_id", add_proc)
    s = {**SETTINGS, "instance_name": None, "name": "Legacy Radarr"}
    del s["instance_name"]
    s["name"] = "Legacy Radarr"
    radarr_upgrade.process_cutoff_upgrades(s, _NO_STOP)
    add_proc.assert_called_once_with("radarr", "Legacy Radarr", "1")

"""Tests for src/primary/apps/eros/missing.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.eros.missing as eros_missing


SETTINGS = {
    "api_url": "http://eros:6969",
    "api_key": "abc123",
    "instance_name": "Eros",
    "monitored_only": True,
    "skip_future_releases": False,
    "hunt_missing_items": 3,
    "search_mode": "movie",
}

_NO_STOP = lambda: False


def _patch(monkeypatch, *, missing=None, search_id=42, is_proc=False):
    monkeypatch.setattr("src.primary.apps.eros.missing.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.eros.missing.load_settings", lambda *a: {})
    monkeypatch.setattr("src.primary.apps.eros.missing.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.eros.missing.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.eros.missing.add_processed_id", MagicMock())
    monkeypatch.setattr("src.primary.apps.eros.missing.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.eros.missing.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.eros.api.get_items_with_missing", lambda *a, **k: missing)
    monkeypatch.setattr("src.primary.apps.eros.api.item_search", lambda *a, **k: search_id)


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, missing=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.check_state_reset", reset)
    eros_missing.process_missing_items(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("eros")


def test_returns_false_when_hunt_zero(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "hunt_missing_items": 0}
    assert eros_missing.process_missing_items(s, _NO_STOP) is False


def test_falls_back_to_hunt_missing_scenes_key(monkeypatch):
    _patch(monkeypatch, missing=[])
    s = {k: v for k, v in SETTINGS.items() if k != "hunt_missing_items"}
    s["hunt_missing_scenes"] = 0
    assert eros_missing.process_missing_items(s, _NO_STOP) is False


def test_returns_false_when_stop_immediately(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Scene"}])
    assert eros_missing.process_missing_items(SETTINGS, lambda: True) is False


def test_returns_false_when_api_returns_none(monkeypatch):
    _patch(monkeypatch, missing=None)
    assert eros_missing.process_missing_items(SETTINGS, _NO_STOP) is False


def test_returns_false_when_api_returns_empty(monkeypatch):
    _patch(monkeypatch, missing=[])
    assert eros_missing.process_missing_items(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_processed(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Scene"}], is_proc=True)
    assert eros_missing.process_missing_items(SETTINGS, _NO_STOP) is False


def test_processes_item_and_returns_true(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Scene"}])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.increment_stat", inc)
    result = eros_missing.process_missing_items(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("eros", "hunted", 1)


def test_adds_processed_id_before_search(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 7, "title": "Scene"}])
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.add_processed_id", add_proc)
    eros_missing.process_missing_items(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("eros", "Eros", "7")


def test_logs_history_after_search(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 5, "title": "Scene Title"}])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.log_processed_media", log_media)
    eros_missing.process_missing_items(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("eros", "Scene Title", 5, "Eros", "missing")


def test_no_stat_increment_when_search_fails(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Scene"}], search_id=None)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.increment_stat", inc)
    result = eros_missing.process_missing_items(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_future_items_filtered_by_air_date(monkeypatch):
    _patch(monkeypatch)
    future = {"id": 1, "title": "Future", "airDateUtc": "2099-01-01T00:00:00Z"}
    monkeypatch.setattr("src.primary.apps.eros.api.get_items_with_missing", lambda *a, **k: [future])
    s = {**SETTINGS, "skip_future_releases": True}
    assert eros_missing.process_missing_items(s, _NO_STOP) is False


def test_items_without_air_date_pass_filter(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "No Date"}])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.increment_stat", inc)
    s = {**SETTINGS, "skip_future_releases": True}
    result = eros_missing.process_missing_items(s, _NO_STOP)
    assert result is True


def test_process_missing_scenes_alias_delegates(monkeypatch):
    _patch(monkeypatch, missing=[{"id": 1, "title": "Scene"}])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.eros.missing.increment_stat", inc)
    result = eros_missing.process_missing_scenes(SETTINGS, _NO_STOP)
    assert result is True

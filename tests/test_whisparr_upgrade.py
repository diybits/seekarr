"""Tests for src/primary/apps/whisparr/upgrade.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.whisparr.upgrade as whisparr_upgrade


SETTINGS = {
    "api_url": "http://whisparr:6969",
    "api_key": "abc123",
    "instance_name": "Whisparr",
    "monitored_only": True,
    "hunt_upgrade_items": 3,
}

_NO_STOP = lambda: False

_ITEM = {
    "id": 1,
    "title": "Scene One",
    "seasonNumber": 1,
    "episodeNumber": 2,
    "series": {"title": "Series One"},
    "episodeFile": {"quality": {"quality": {"name": "HD"}}},
}


def _patch(monkeypatch, *, eligible=None, search_id=42, is_proc=False):
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.add_processed_id", MagicMock())
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_cutoff_unmet_items", lambda *a, **k: eligible)
    monkeypatch.setattr("src.primary.apps.whisparr.api.item_search", lambda *a, **k: search_id)


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, eligible=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.check_state_reset", reset)
    whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("whisparr")


def test_returns_false_when_hunt_upgrade_zero(monkeypatch):
    _patch(monkeypatch)
    s = {**SETTINGS, "hunt_upgrade_items": 0}
    assert whisparr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_falls_back_to_hunt_upgrade_scenes_key(monkeypatch):
    _patch(monkeypatch, eligible=[])
    s = {k: v for k, v in SETTINGS.items() if k != "hunt_upgrade_items"}
    s["hunt_upgrade_scenes"] = 0
    assert whisparr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_returns_false_when_stop_before_start(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM])
    assert whisparr_upgrade.process_cutoff_upgrades(SETTINGS, lambda: True) is False


def test_returns_false_when_eligible_none(monkeypatch):
    _patch(monkeypatch, eligible=None)
    assert whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_eligible_empty(monkeypatch):
    _patch(monkeypatch, eligible=[])
    assert whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_processed(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM], is_proc=True)
    assert whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_processes_item_and_returns_true(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.increment_stat", inc)
    result = whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("whisparr", "upgraded", 1)


def test_adds_processed_id_before_search(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM])
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.add_processed_id", add_proc)
    whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("whisparr", "Whisparr", "1")


def test_logs_history_with_series_and_episode(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.log_processed_media", log_media)
    whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with(
        "whisparr", "Series One - S01E02 - Scene One", 1, "Whisparr", "upgrade"
    )


def test_search_failure_does_not_increment_stat(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM], search_id=None)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.whisparr.upgrade.increment_stat", inc)
    result = whisparr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_stop_mid_loop_aborts(monkeypatch):
    _patch(monkeypatch, eligible=[_ITEM])
    calls = iter([False, False, True])
    result = whisparr_upgrade.process_cutoff_upgrades(SETTINGS, lambda: next(calls, True))
    assert result is False

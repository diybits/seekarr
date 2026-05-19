"""Tests for src/primary/apps/readarr/upgrade.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.readarr.upgrade as readarr_upgrade


SETTINGS = {
    "api_url": "http://readarr:8787",
    "api_key": "abc123",
    "instance_name": "Readarr",
    "monitored_only": True,
    "skip_future_releases": False,
    "hunt_upgrade_books": 5,
}

_NO_STOP = lambda: False

_BOOK = {"id": 10, "title": "Book One", "authorName": "Author One", "authorId": 1}


def _patch(monkeypatch, *, eligible=None, search_result=99, is_proc=False,
           author_details=None):
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.load_settings", lambda *a: {"api_timeout": 120})
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.add_processed_id", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.api.get_cutoff_unmet_books", lambda *a, **k: eligible)
    monkeypatch.setattr("src.primary.apps.readarr.api.search_books", lambda *a, **k: search_result)
    monkeypatch.setattr("src.primary.apps.readarr.api.get_author_details",
                        lambda *a, **k: author_details or {"authorName": "Author One"})


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, eligible=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.check_state_reset", reset)
    readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("readarr")


def test_returns_false_when_eligible_none(monkeypatch):
    _patch(monkeypatch, eligible=None)
    assert readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_eligible_empty(monkeypatch):
    _patch(monkeypatch, eligible=[])
    assert readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_returns_false_when_all_processed(monkeypatch):
    _patch(monkeypatch, eligible=[_BOOK], is_proc=True)
    assert readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP) is False


def test_processes_book_and_returns_true(monkeypatch):
    _patch(monkeypatch, eligible=[_BOOK])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.increment_stat", inc)
    result = readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("readarr", "upgraded")


def test_adds_processed_id_before_search(monkeypatch):
    _patch(monkeypatch, eligible=[_BOOK])
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.add_processed_id", add_proc)
    readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("readarr", "Readarr", "10")


def test_logs_history_per_book(monkeypatch):
    _patch(monkeypatch, eligible=[_BOOK])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.log_processed_media", log_media)
    readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("readarr", "Author One - Book One", 10, "Readarr", "upgrade")


def test_search_failure_returns_false(monkeypatch):
    _patch(monkeypatch, eligible=[_BOOK], search_result=None)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.increment_stat", inc)
    result = readarr_upgrade.process_cutoff_upgrades(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_future_book_filtered_by_release_date(monkeypatch):
    future_book = {**_BOOK, "releaseDate": "2099-12-01T00:00:00Z"}
    _patch(monkeypatch, eligible=[future_book])
    s = {**SETTINGS, "skip_future_releases": True}
    assert readarr_upgrade.process_cutoff_upgrades(s, _NO_STOP) is False


def test_past_book_passes_release_date_filter(monkeypatch):
    past_book = {**_BOOK, "releaseDate": "2020-01-01T00:00:00Z"}
    _patch(monkeypatch, eligible=[past_book])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.increment_stat", inc)
    s = {**SETTINGS, "skip_future_releases": True}
    result = readarr_upgrade.process_cutoff_upgrades(s, _NO_STOP)
    assert result is True
    inc.assert_called_once()


def test_book_without_release_date_included(monkeypatch):
    book_no_date = {k: v for k, v in _BOOK.items() if k != "releaseDate"}
    _patch(monkeypatch, eligible=[book_no_date])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.upgrade.increment_stat", inc)
    s = {**SETTINGS, "skip_future_releases": True}
    result = readarr_upgrade.process_cutoff_upgrades(s, _NO_STOP)
    assert result is True
    inc.assert_called_once()

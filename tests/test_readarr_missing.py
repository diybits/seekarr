"""Tests for src/primary/apps/readarr/missing.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.readarr.missing as readarr_missing


SETTINGS = {
    "api_url": "http://readarr:8787",
    "api_key": "abc123",
    "instance_name": "Readarr",
    "monitored_only": True,
    "skip_future_releases": False,
    "hunt_missing_books": 5,
}

_NO_STOP = lambda: False

_BOOK = {"id": 10, "title": "Book One", "authorId": 1}
_AUTHOR = {"authorName": "Author One"}


def _patch(monkeypatch, *, missing=None, search_result={"id": 99}, is_proc=False,
           author_details=None):
    monkeypatch.setattr("src.primary.apps.readarr.missing.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.readarr.missing.check_state_reset", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.missing.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.readarr.missing.add_processed_id", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.missing.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.missing.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.readarr.api.load_settings", lambda *a: {})
    monkeypatch.setattr("src.primary.apps.readarr.api.get_wanted_missing_books", lambda *a, **k: missing)
    monkeypatch.setattr("src.primary.apps.readarr.api.get_author_details",
                        lambda *a, **k: author_details or _AUTHOR)
    monkeypatch.setattr("src.primary.apps.readarr.api.search_books", lambda *a, **k: search_result)


def test_calls_check_state_reset(monkeypatch):
    _patch(monkeypatch, missing=[])
    reset = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.check_state_reset", reset)
    readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    reset.assert_called_once_with("readarr")


def test_returns_false_when_api_returns_none(monkeypatch):
    _patch(monkeypatch, missing=None)
    assert readarr_missing.process_missing_books(SETTINGS, _NO_STOP) is False


def test_returns_false_when_api_returns_empty(monkeypatch):
    _patch(monkeypatch, missing=[])
    assert readarr_missing.process_missing_books(SETTINGS, _NO_STOP) is False


def test_returns_false_when_author_already_processed(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK], is_proc=True)
    assert readarr_missing.process_missing_books(SETTINGS, _NO_STOP) is False


def test_processes_book_and_returns_true(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.increment_stat", inc)
    result = readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    assert result is True
    inc.assert_called_once_with("readarr", "hunted")


def test_adds_author_to_processed_id(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK])
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.add_processed_id", add_proc)
    readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    add_proc.assert_called_once_with("readarr", "Readarr", "1")


def test_logs_history_per_book(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK])
    log_media = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.log_processed_media", log_media)
    readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    log_media.assert_called_once_with("readarr", "Author One - Book One", 10, "Readarr", "missing")


def test_no_stat_when_search_fails(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK], search_result=None)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.increment_stat", inc)
    result = readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()


def test_stop_at_loop_start_aborts(monkeypatch):
    _patch(monkeypatch, missing=[_BOOK])
    result = readarr_missing.process_missing_books(SETTINGS, lambda: True)
    assert result is False


def test_groups_multiple_books_by_author(monkeypatch):
    books = [
        {"id": 10, "title": "Book One", "authorId": 1},
        {"id": 11, "title": "Book Two", "authorId": 1},
        {"id": 20, "title": "Other Book", "authorId": 2},
    ]
    _patch(monkeypatch, missing=books)
    add_proc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.add_processed_id", add_proc)
    s = {**SETTINGS, "hunt_missing_books": 10}
    readarr_missing.process_missing_books(s, _NO_STOP)
    called_ids = {call.args[2] for call in add_proc.call_args_list}
    assert "1" in called_ids
    assert "2" in called_ids


def test_books_without_author_id_are_skipped(monkeypatch):
    book_no_author = {"id": 99, "title": "Orphan Book"}
    _patch(monkeypatch, missing=[book_no_author])
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.readarr.missing.increment_stat", inc)
    result = readarr_missing.process_missing_books(SETTINGS, _NO_STOP)
    assert result is False
    inc.assert_not_called()

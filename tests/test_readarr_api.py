"""Tests for src/primary/apps/readarr/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch
import pytest
import requests as _requests

import src.primary.apps.readarr.api as readarr_api


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    mock.content = b'{"ok": true}'
    mock.headers = {"Content-Type": "application/json"}
    mock.raise_for_status.return_value = None
    return mock


def _capture_session_get(json_data, captured):
    def _get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _get


def _capture_session_post(json_data, captured):
    def _post(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _post


# ── arr_request — SSL verification ────────────────────────────────────────────

def test_arr_request_passes_verify_false_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        readarr_api.arr_request("system/status", api_url="http://readarr:8787", api_key="key", api_timeout=30)
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        readarr_api.arr_request("system/status", api_url="http://readarr:8787", api_key="key", api_timeout=30)
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        readarr_api.arr_request("system/status", api_url="http://readarr:8787", api_key="key", api_timeout=30)
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_arr_request_uses_v1_api_path(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        readarr_api.arr_request("system/status", api_url="http://readarr:8787", api_key="key", api_timeout=30)
    assert "/api/v1/" in captured.get("url", "")


def test_arr_request_returns_none_on_request_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(readarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("conn")):
        result = readarr_api.arr_request("system/status", api_url="http://readarr:8787", api_key="key", api_timeout=30)
    assert result is None


# ── check_connection ───────────────────────────────────────────────────────────

def test_check_connection_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        result = readarr_api.check_connection("http://readarr:8787", "key", 30)
    assert result is True
    assert captured.get("verify") is False


def test_check_connection_respects_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"version": "0.3.0"}, captured)):
        result = readarr_api.check_connection("http://readarr:8787", "key", 30)
    assert result is True
    assert captured.get("verify") is True


def test_check_connection_returns_false_on_request_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(readarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("conn refused")):
        result = readarr_api.check_connection("http://readarr:8787", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_empty_url():
    result = readarr_api.check_connection("", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_invalid_scheme():
    result = readarr_api.check_connection("readarr:8787", "key", 30)
    assert result is False


# ── get_download_queue_size ────────────────────────────────────────────────────

def test_get_download_queue_size_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 3}, captured)):
        result = readarr_api.get_download_queue_size("http://readarr:8787", "key", 30)
    assert captured.get("verify") is False
    assert result == 3


def test_get_download_queue_size_returns_zero_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(readarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("conn")):
        result = readarr_api.get_download_queue_size("http://readarr:8787", "key", 30)
    assert result == 0


# ── get_wanted_missing_books ───────────────────────────────────────────────────

def test_get_wanted_missing_books_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_get(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"records": [{"id": 1}], "totalRecords": 1})
    with patch.object(readarr_api.session, "get", side_effect=mock_get):
        result = readarr_api.get_wanted_missing_books("http://readarr:8787", "key", 30)
    assert captured.get("verify") is False
    assert len(result) == 1


def test_get_wanted_missing_books_returns_empty_for_invalid_url():
    result = readarr_api.get_wanted_missing_books("readarr:8787", "key", 30)
    assert result == []


# ── get_author_details ─────────────────────────────────────────────────────────

def test_get_author_details_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(readarr_api.session, "get", side_effect=_capture_session_get({"id": 5, "authorName": "Test Author"}, captured)):
        result = readarr_api.get_author_details("http://readarr:8787", "key", 5, 30)
    assert captured.get("verify") is False
    assert result["authorName"] == "Test Author"


def test_get_author_details_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(readarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("conn")):
        result = readarr_api.get_author_details("http://readarr:8787", "key", 5, 30)
    assert result is None


# ── search_books ───────────────────────────────────────────────────────────────

def test_search_books_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(readarr_api.session, "post", side_effect=_capture_session_post({"id": 42, "name": "BookSearch"}, captured)):
        result = readarr_api.search_books("http://readarr:8787", "key", [1, 2], 30)
    assert captured.get("verify") is False
    assert result["id"] == 42


def test_search_books_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.readarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(readarr_api.session, "post", side_effect=_requests.exceptions.ConnectionError("conn")):
        result = readarr_api.search_books("http://readarr:8787", "key", [1], 30)
    assert result is None

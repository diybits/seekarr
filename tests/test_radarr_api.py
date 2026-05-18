"""Tests for src/primary/apps/radarr/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

import src.primary.apps.radarr.api as radarr_api


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    mock.content = b'{"ok": true}'
    mock.raise_for_status.return_value = None
    return mock


def _capture_session_get(json_data, captured):
    def _get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _get


# ── arr_request — SSL verification ────────────────────────────────────────────

def test_arr_request_passes_verify_false_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "5.0.0"}, captured)):
        radarr_api.arr_request("http://radarr:7878", "key", 30, "system/status")
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "5.0.0"}, captured)):
        radarr_api.arr_request("http://radarr:7878", "key", 30, "system/status")
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "5.0.0"}, captured)):
        radarr_api.arr_request("http://radarr:7878", "key", 30, "system/status")
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_arr_request_passes_params_to_get(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 0}, captured)):
        radarr_api.arr_request("http://radarr:7878", "key", 30, "queue", params={"page": 1, "pageSize": 1000})
    assert captured.get("params") == {"page": 1, "pageSize": 1000}


# ── check_connection — routed through arr_request ────────────────────────────

def test_check_connection_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "5.0.0"}, captured)):
        result = radarr_api.check_connection("http://radarr:7878", "key", 30)
    assert result is True
    assert captured.get("verify") is False


def test_check_connection_respects_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "5.0.0"}, captured)):
        result = radarr_api.check_connection("http://radarr:7878", "key", 30)
    assert result is True
    assert captured.get("verify") is True


def test_check_connection_returns_false_on_request_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(radarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("conn refused")):
        result = radarr_api.check_connection("http://radarr:7878", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_empty_url():
    result = radarr_api.check_connection("", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_missing_scheme():
    result = radarr_api.check_connection("radarr:7878", "key", 30)
    assert result is False


def test_check_connection_returns_false_when_no_version_in_response(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"unexpected": "data"}, {})):
        result = radarr_api.check_connection("http://radarr:7878", "key", 30)
    assert result is False


# ── get_download_queue_size — routed through arr_request ──────────────────────

def test_get_download_queue_size_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 12}, captured)):
        result = radarr_api.get_download_queue_size("http://radarr:7878", "key", 30)
    assert captured.get("verify") is False
    assert result == 12


def test_get_download_queue_size_returns_negative_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(radarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("timeout")):
        result = radarr_api.get_download_queue_size("http://radarr:7878", "key", 30)
    assert result == -1


def test_get_download_queue_size_returns_negative_for_empty_credentials():
    result = radarr_api.get_download_queue_size("", "", 30)
    assert result == -1

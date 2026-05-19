"""Tests for src/primary/apps/lidarr/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch
import logging

import pytest

import src.primary.apps.lidarr.api as lidarr_api


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


def _capture_session_request(json_data, captured):
    def _request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured.update(kwargs)
        return _mock_response(json_data)
    return _request


# ── arr_request — SSL verification ────────────────────────────────────────────

def test_arr_request_passes_verify_false_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        lidarr_api.arr_request("http://lidarr:8686", "key", 30, "system/status")
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        lidarr_api.arr_request("http://lidarr:8686", "key", 30, "system/status")
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        lidarr_api.arr_request("http://lidarr:8686", "key", 30, "system/status")
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_arr_request_uses_v1_api_path(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        lidarr_api.arr_request("http://lidarr:8686", "key", 30, "system/status")
    assert "/api/v1/" in captured.get("url", "")


# ── get_system_status — routed through arr_request ───────────────────────────

def test_get_system_status_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        result = lidarr_api.get_system_status("http://lidarr:8686", "key", 30)
    assert captured.get("verify") is False
    assert result.get("version") == "2.0.0"


def test_get_system_status_respects_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        result = lidarr_api.get_system_status("http://lidarr:8686", "key", 30)
    assert captured.get("verify") is True


def test_get_system_status_returns_empty_dict_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(lidarr_api.session, "request", side_effect=Exception("conn refused")):
        result = lidarr_api.get_system_status("http://lidarr:8686", "key", 30)
    assert result == {}


# ── check_connection — uses get_system_status → arr_request ──────────────────

def test_check_connection_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        result = lidarr_api.check_connection("http://lidarr:8686", "key", 30)
    assert result is True
    assert captured.get("verify") is False


def test_check_connection_respects_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"version": "2.0.0"}, captured)):
        result = lidarr_api.check_connection("http://lidarr:8686", "key", 30)
    assert result is True
    assert captured.get("verify") is True


def test_check_connection_returns_false_on_request_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(lidarr_api.session, "request", side_effect=Exception("conn refused")):
        result = lidarr_api.check_connection("http://lidarr:8686", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_empty_url():
    result = lidarr_api.check_connection("", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_empty_api_key():
    result = lidarr_api.check_connection("http://lidarr:8686", "", 30)
    assert result is False


def test_check_connection_returns_false_when_no_version_in_response(monkeypatch):
    monkeypatch.setattr("src.primary.apps.lidarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(lidarr_api.session, "request", side_effect=_capture_session_request({"unexpected": "data"}, {})):
        result = lidarr_api.check_connection("http://lidarr:8686", "key", 30)
    assert result is False

"""Tests for src/primary/apps/sonarr/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch, call

import pytest

import src.primary.apps.sonarr.api as sonarr_api


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.content = b'{"ok": true}'
    mock.raise_for_status.return_value = None
    return mock


def _capture_session_get(json_data, captured):
    """Returns a side_effect that records kwargs and returns a mock response."""
    def _get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _get


# ── arr_request — SSL verification ────────────────────────────────────────────

def test_arr_request_passes_verify_false_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"version": "4.0.0"}, captured)):
        sonarr_api.arr_request("http://sonarr:8989", "key", 30, "system/status")
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"version": "4.0.0"}, captured)):
        sonarr_api.arr_request("http://sonarr:8989", "key", 30, "system/status")
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"version": "4.0.0"}, captured)):
        sonarr_api.arr_request("http://sonarr:8989", "key", 30, "system/status")
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_arr_request_passes_params_to_get(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"records": []}, captured)):
        sonarr_api.arr_request("http://sonarr:8989", "key", 30, "queue", params={"page": 1, "pageSize": 10})
    assert captured.get("params") == {"page": 1, "pageSize": 10}


def test_arr_request_returns_none_on_request_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "get", side_effect=Exception("connection refused")):
        result = sonarr_api.arr_request("http://sonarr:8989", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_for_missing_url():
    result = sonarr_api.arr_request("", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_for_missing_key():
    result = sonarr_api.arr_request("http://sonarr:8989", "", 30, "system/status")
    assert result is None


# ── search_episode — routed through arr_request ───────────────────────────────

def test_search_episode_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_post(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"id": 42})
    with patch.object(sonarr_api.session, "post", side_effect=mock_post):
        result = sonarr_api.search_episode("http://sonarr:8989", "key", 30, [1, 2])
    assert captured.get("verify") is False
    assert result == 42


def test_search_episode_returns_none_for_empty_list():
    result = sonarr_api.search_episode("http://sonarr:8989", "key", 30, [])
    assert result is None


def test_search_episode_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "post", return_value=_mock_response({})):
        result = sonarr_api.search_episode("http://sonarr:8989", "key", 30, [1])
    assert result is None


# ── get_command_status — routed through arr_request ───────────────────────────

def test_get_command_status_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"id": 5, "status": "completed"}, captured)):
        result = sonarr_api.get_command_status("http://sonarr:8989", "key", 30, 5)
    assert captured.get("verify") is False
    assert result["status"] == "completed"


def test_get_command_status_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "get", side_effect=Exception("timeout")):
        result = sonarr_api.get_command_status("http://sonarr:8989", "key", 30, 5)
    assert result is None


# ── get_download_queue_size — routed through arr_request ──────────────────────

def test_get_download_queue_size_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 7, "records": []}, captured)):
        result = sonarr_api.get_download_queue_size("http://sonarr:8989", "key", 30)
    assert captured.get("verify") is False
    assert result == 7


def test_get_download_queue_size_returns_negative_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "get", side_effect=Exception("conn")):
        result = sonarr_api.get_download_queue_size("http://sonarr:8989", "key", 30)
    assert result == -1


# ── get_series_by_id — routed through arr_request ────────────────────────────

def test_get_series_by_id_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"id": 10, "title": "Breaking Bad"}, captured)):
        result = sonarr_api.get_series_by_id("http://sonarr:8989", "key", 30, 10)
    assert captured.get("verify") is False
    assert result["title"] == "Breaking Bad"


def test_get_series_by_id_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "get", side_effect=Exception("timeout")):
        result = sonarr_api.get_series_by_id("http://sonarr:8989", "key", 30, 10)
    assert result is None


# ── search_season — routed through arr_request ───────────────────────────────

def test_search_season_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_post(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"id": 99})
    with patch.object(sonarr_api.session, "post", side_effect=mock_post):
        result = sonarr_api.search_season("http://sonarr:8989", "key", 30, 10, 2)
    assert captured.get("verify") is False
    assert result == 99


def test_search_season_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "post", side_effect=Exception("conn")):
        result = sonarr_api.search_season("http://sonarr:8989", "key", 30, 10, 2)
    assert result is None


# ── get_cutoff_unmet_episodes_random_page — routed through arr_request ────────

def test_cutoff_random_page_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    calls = []
    def mock_get(url, **kwargs):
        calls.append(kwargs.get("verify"))
        if len(calls) == 1:
            return _mock_response({"totalRecords": 5, "records": []})
        return _mock_response({"totalRecords": 5, "records": [
            {"id": i, "monitored": True, "series": {"monitored": True}} for i in range(5)
        ]})
    with patch.object(sonarr_api.session, "get", side_effect=mock_get):
        sonarr_api.get_cutoff_unmet_episodes_random_page("http://sonarr:8989", "key", 30, False, 3)
    assert all(v is False for v in calls)


def test_cutoff_random_page_returns_empty_when_no_records(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(sonarr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 0, "records": []}, {})):
        result = sonarr_api.get_cutoff_unmet_episodes_random_page("http://sonarr:8989", "key", 30, False, 3)
    assert result == []


# ── get_missing_episodes_random_page — routed through arr_request ─────────────

def test_missing_random_page_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    calls = []
    def mock_get(url, **kwargs):
        calls.append(kwargs.get("verify"))
        if len(calls) == 1:
            return _mock_response({"totalRecords": 5, "records": []})
        return _mock_response({"totalRecords": 5, "records": [
            {"id": i, "monitored": True, "series": {"monitored": True}} for i in range(5)
        ]})
    with patch.object(sonarr_api.session, "get", side_effect=mock_get):
        sonarr_api.get_missing_episodes_random_page("http://sonarr:8989", "key", 30, False, 3)
    assert all(v is False for v in calls)


# ── get_missing_episodes — session.get with SSL ───────────────────────────────

def test_get_missing_episodes_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_get(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"records": [], "totalRecords": 0})
    with patch.object(sonarr_api.session, "get", side_effect=mock_get):
        sonarr_api.get_missing_episodes("http://sonarr:8989", "key", 30, False)
    assert captured.get("verify") is False


# ── get_cutoff_unmet_episodes — session.get with SSL ─────────────────────────

def test_get_cutoff_unmet_episodes_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_get(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"records": [], "totalRecords": 0})
    with patch.object(sonarr_api.session, "get", side_effect=mock_get):
        sonarr_api.get_cutoff_unmet_episodes("http://sonarr:8989", "key", 30, False)
    assert captured.get("verify") is False


# ── get_series_with_missing_episodes — arr_request for episode call ───────────

def test_get_series_with_missing_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_ssl_verify_setting", lambda: False)
    calls = []
    def mock_get(url, **kwargs):
        calls.append(kwargs.get("verify"))
        params = kwargs.get("params", {})
        if "seriesId" in (params or {}):
            return _mock_response([{"id": 1, "hasFile": False, "monitored": True, "seasonNumber": 1}])
        return _mock_response([{"id": 1, "title": "Show", "monitored": True}])
    with patch.object(sonarr_api.session, "get", side_effect=mock_get):
        sonarr_api.get_series_with_missing_episodes("http://sonarr:8989", "key", 30, True, 1, False)
    assert all(v is False for v in calls)

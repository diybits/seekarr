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


# ── get_cutoff_unmet_movies — native wanted/cutoff endpoint ──────────────────

def _paged_session_get(pages_by_key, captured_calls):
    """Mock session.get that serves a different page per (monitored, page) key."""
    def _get(url, **kwargs):
        params = kwargs.get("params", {})
        captured_calls.append({
            "url": url,
            "params": dict(params),
            "verify": kwargs.get("verify"),
        })
        key = (params.get("monitored"), params.get("page", 1))
        return _mock_response(pages_by_key.get(key, {"records": [], "totalRecords": 0}))
    return _get


def test_get_cutoff_unmet_movies_paginates(monkeypatch):
    """All pages are fetched and concatenated; monitored=True is sent."""
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: False)
    page1 = {"records": [{"id": i, "title": f"m{i}"} for i in range(1000)], "totalRecords": 1500}
    page2 = {"records": [{"id": i, "title": f"m{i}"} for i in range(1000, 1500)], "totalRecords": 1500}
    calls = []
    with patch.object(radarr_api.session, "get", side_effect=_paged_session_get({
        (True, 1): page1,
        (True, 2): page2,
    }, calls)):
        result = radarr_api.get_cutoff_unmet_movies("http://radarr:7878", "key", 30, monitored_only=True)
    assert len(result) == 1500
    assert result[0]["id"] == 0 and result[-1]["id"] == 1499
    assert all(c["url"] == "http://radarr:7878/api/v3/wanted/cutoff" for c in calls)
    assert all(c["params"]["monitored"] is True for c in calls)
    assert [c["params"]["page"] for c in calls] == [1, 2]
    assert all(c["verify"] is False for c in calls)


def test_get_cutoff_unmet_movies_includes_unmonitored_when_requested(monkeypatch):
    """monitored_only=False does one pass per monitored value (true and false)."""
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    calls = []
    with patch.object(radarr_api.session, "get", side_effect=_paged_session_get({
        (True, 1): {"records": [{"id": 1}, {"id": 2}], "totalRecords": 2},
        (False, 1): {"records": [{"id": 3}, {"id": 4}, {"id": 5}], "totalRecords": 3},
    }, calls)):
        result = radarr_api.get_cutoff_unmet_movies("http://radarr:7878", "key", 30, monitored_only=False)
    assert [m["id"] for m in result] == [1, 2, 3, 4, 5]
    # One page fetch for monitored=True, then one for monitored=False.
    assert [(c["params"]["monitored"], c["params"]["page"]) for c in calls] == [(True, 1), (False, 1)]


def test_get_cutoff_unmet_movies_empty_when_no_records(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    calls = []
    with patch.object(radarr_api.session, "get", side_effect=_paged_session_get({
        (True, 1): {"records": [], "totalRecords": 0},
    }, calls)):
        result = radarr_api.get_cutoff_unmet_movies("http://radarr:7878", "key", 30, monitored_only=True)
    assert result == []
    assert len(calls) == 1  # no second page requested


def test_get_cutoff_unmet_movies_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(radarr_api.session, "get", side_effect=_requests.exceptions.ConnectionError("timeout")):
        result = radarr_api.get_cutoff_unmet_movies("http://radarr:7878", "key", 30, monitored_only=True)
    assert result is None


# ── Shared client delegation (T6b) ───────────────────────────────────────────

def test_session_is_shared_arr_client_session():
    import src.primary.utils.arr_client as arr_client
    assert radarr_api.session is arr_client.session


def test_arr_request_uses_shared_user_agent(monkeypatch):
    import src.primary.utils.arr_client as arr_client
    monkeypatch.setattr("src.primary.apps.radarr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(radarr_api.session, "get", side_effect=_capture_session_get({"version": "6.0.0"}, captured)):
        radarr_api.arr_request("http://radarr:7878", "key", 30, "system/status")
    # UA comes from the shared version source (version.txt), not a hardcoded string
    assert captured["headers"]["User-Agent"] == arr_client.get_user_agent()
    assert "Seekarr/" in captured["headers"]["User-Agent"]

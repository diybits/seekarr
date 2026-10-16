"""Tests for src/primary/apps/whisparr/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch
import requests

import src.primary.apps.whisparr.api as whisparr_api


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    mock.content = b'{"ok": true}'
    mock.headers = {"Content-Type": "application/json"}
    def _raise_for_status():
        if status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {status_code}")
    mock.raise_for_status.side_effect = _raise_for_status
    return mock


def _capture_session_get(json_data, captured):
    def _get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _get


# ── arr_request — SSL verification (primary path) ──────────────────────────────

def test_arr_request_passes_verify_false_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0"}, captured)):
        whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0"}, captured)):
        whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0"}, captured)):
        whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


# ── arr_request — URL path correctness ───────────────────────────────────────

def test_arr_request_uses_v3_primary_path(monkeypatch):
    """Whisparr v2 serves its REST API under /api/v3/ — that is the only path tried."""
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0"}, captured)):
        whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    assert captured["url"] == "http://whisparr:6969/api/v3/system/status"


def test_arr_request_makes_single_request_on_404(monkeypatch):
    """No legacy /api/ path is tried — a 404 on the v3 URL is reported as-is."""
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    calls = []
    def mock_get(url, **kwargs):
        calls.append(url)
        return _mock_response({"error": "not found"}, 404)
    with patch.object(whisparr_api.session, "get", side_effect=mock_get):
        result = whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    assert calls == ["http://whisparr:6969/api/v3/system/status"]
    assert result is None


# ── get_download_queue_size — totalRecords from paginated queue ─────────────

def test_get_download_queue_size_reads_total_records(monkeypatch):
    """Queue size comes from totalRecords, not len(records) of the first page."""
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"totalRecords": 250, "records": [{"id": 1}]}, captured)):
        result = whisparr_api.get_download_queue_size("http://whisparr:6969", "key", 30)
    assert captured.get("verify") is False
    assert captured["url"] == "http://whisparr:6969/api/v3/queue"
    assert captured.get("params") == {"page": 1, "pageSize": 1}
    assert result == 250


def test_get_download_queue_size_returns_minus_one_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api.session, "get", side_effect=requests.exceptions.ConnectionError("timeout")):
        result = whisparr_api.get_download_queue_size("http://whisparr:6969", "key", 30)
    assert result == -1


# ── item_search — SSL verification ────────────────────────────────────────────

def test_item_search_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_post(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response({"id": 42})
    with patch.object(whisparr_api.session, "post", side_effect=mock_post):
        result = whisparr_api.item_search("http://whisparr:6969", "key", 30, [1, 2])
    assert captured.get("verify") is False
    assert captured["url"] == "http://whisparr:6969/api/v3/command"
    assert result == 42


def test_item_search_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    def mock_post(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"id": 42})
    with patch.object(whisparr_api.session, "post", side_effect=mock_post):
        whisparr_api.item_search("http://whisparr:6969", "key", 30, [1])
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_item_search_returns_none_when_no_item_ids(monkeypatch):
    """An empty ID list must not trigger a search request."""
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api.session, "post", side_effect=AssertionError("should not be called")):
        result = whisparr_api.item_search("http://whisparr:6969", "key", 30, [])
    assert result is None


def test_item_search_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api.session, "post", side_effect=Exception("conn")):
        result = whisparr_api.item_search("http://whisparr:6969", "key", 30, [1])
    assert result is None


# ── get_command_status — SSL verification ─────────────────────────────────────

def test_get_command_status_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"id": 5, "status": "completed"}, captured)):
        result = whisparr_api.get_command_status("http://whisparr:6969", "key", 30, 5)
    assert captured.get("verify") is False
    assert captured["url"] == "http://whisparr:6969/api/v3/command/5"
    assert result["status"] == "completed"


def test_get_command_status_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api.session, "get", side_effect=Exception("timeout")):
        result = whisparr_api.get_command_status("http://whisparr:6969", "key", 30, 5)
    assert result is None


# ── check_connection — SSL verification ───────────────────────────────────────

def test_check_connection_respects_ssl_disabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0.0"}, captured)):
        result = whisparr_api.check_connection("http://whisparr:6969", "key", 30)
    assert result is True
    assert captured.get("verify") is False


def test_check_connection_respects_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0.0"}, captured)):
        result = whisparr_api.check_connection("http://whisparr:6969", "key", 30)
    assert result is True
    assert captured.get("verify") is True


def test_check_connection_makes_no_fallback_request(monkeypatch):
    """When arr_request fails, check_connection gives up without any extra direct request."""
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: False)
    with patch.object(whisparr_api, "arr_request", return_value=None), \
         patch.object(whisparr_api.session, "get", side_effect=AssertionError("direct session.get should not be called")):
        result = whisparr_api.check_connection("http://whisparr:6969", "key", 30)
    assert result is False


def test_check_connection_returns_false_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api, "arr_request", return_value=None), \
         patch.object(whisparr_api.session, "get", side_effect=Exception("conn refused")):
        result = whisparr_api.check_connection("http://whisparr:6969", "key", 30)
    assert result is False


def test_check_connection_returns_false_for_unexpected_version(monkeypatch):
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "3.0.0"}, {})):
        result = whisparr_api.check_connection("http://whisparr:6969", "key", 30)
    assert result is False


# ── Shared client delegation (T6d) ───────────────────────────────────────────

def test_session_is_shared_arr_client_session():
    import src.primary.utils.arr_client as arr_client
    assert whisparr_api.session is arr_client.session


def test_arr_request_uses_shared_user_agent(monkeypatch):
    import src.primary.utils.arr_client as arr_client
    monkeypatch.setattr("src.primary.apps.whisparr.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(whisparr_api.session, "get", side_effect=_capture_session_get({"version": "2.0.0.0"}, captured)):
        whisparr_api.arr_request("http://whisparr:6969", "key", 30, "system/status")
    # UA comes from the shared version source (version.txt), not a hardcoded string
    assert captured["headers"]["User-Agent"] == arr_client.get_user_agent()
    assert "/api/v3/" in captured["url"]

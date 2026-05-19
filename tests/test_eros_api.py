"""Tests for src/primary/apps/eros/api.py — SSL compliance and arr_request routing."""
from unittest.mock import MagicMock, patch
import pytest

import src.primary.apps.eros.api as eros_api


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
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
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get({"version": "3.0"}, captured)):
        eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert captured.get("verify") is False


def test_arr_request_passes_verify_true_when_ssl_enabled(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get({"version": "3.0"}, captured)):
        eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert captured.get("verify") is True


def test_arr_request_sends_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get({"version": "3.0"}, captured)):
        eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert "Seekarr" in captured.get("headers", {}).get("User-Agent", "")


def test_arr_request_uses_v3_url_path(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get({"version": "3.0"}, captured)):
        eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert captured["url"] == "http://eros:6969/api/v3/system/status"


def test_arr_request_returns_none_when_no_url(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.arr_request("", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.arr_request("http://eros:6969", "", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_for_invalid_url(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.arr_request("not-a-url", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    import requests as req_lib
    mock = _mock_response({}, 500)
    mock.raise_for_status.side_effect = req_lib.exceptions.HTTPError("500")
    with patch.object(eros_api.session, "get", return_value=mock):
        result = eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_on_connection_error(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    import requests as req_lib
    with patch.object(eros_api.session, "get", side_effect=req_lib.exceptions.ConnectionError("refused")):
        result = eros_api.arr_request("http://eros:6969", "key", 30, "system/status")
    assert result is None


def test_arr_request_post_uses_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    def mock_post(url, **kwargs):
        captured.update(kwargs)
        return _mock_response({"id": 1})
    with patch.object(eros_api.session, "post", side_effect=mock_post):
        eros_api.arr_request("http://eros:6969", "key", 30, "command", "POST", {"name": "Test"})
    assert captured.get("verify") is False


# ── get_download_queue_size ───────────────────────────────────────────────────

def test_get_download_queue_size_with_records_dict(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 1}, {"id": 2}]}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get(payload, {})):
        result = eros_api.get_download_queue_size("http://eros:6969", "key", 30)
    assert result == 2


def test_get_download_queue_size_with_list_response(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get([{"id": 1}], {})):
        result = eros_api.get_download_queue_size("http://eros:6969", "key", 30)
    assert result == 1


def test_get_download_queue_size_returns_minus_one_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.get_download_queue_size("http://eros:6969", "key", 30)
    assert result == -1


# ── get_items_with_missing ────────────────────────────────────────────────────

def test_get_items_with_missing_movie_mode_list(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    items = [{"id": 1, "hasFile": False, "monitored": True}, {"id": 2, "hasFile": True, "monitored": True}]
    with patch.object(eros_api, "arr_request", return_value=items):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "movie")
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_get_items_with_missing_movie_mode_dict_records(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 1, "hasFile": False, "monitored": True}]}
    with patch.object(eros_api, "arr_request", return_value=payload):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "movie")
    assert len(result) == 1


def test_get_items_with_missing_filters_monitored(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    items = [
        {"id": 1, "hasFile": False, "monitored": True},
        {"id": 2, "hasFile": False, "monitored": False},
    ]
    with patch.object(eros_api, "arr_request", return_value=items):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, True, "movie")
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_get_items_with_missing_scene_mode(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 10, "monitored": True}]}
    with patch.object(eros_api, "arr_request", return_value=payload):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "scene")
    assert result == [{"id": 10, "monitored": True}]


def test_get_items_with_missing_scene_fallback_to_movie(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    items = [{"id": 5, "hasFile": False, "monitored": True}]
    calls = []
    def mock_arr(url, key, timeout, endpoint, **kwargs):
        calls.append(endpoint)
        if "scene" in endpoint:
            return None
        return items
    with patch.object(eros_api, "arr_request", side_effect=mock_arr):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "scene")
    assert any("scene" in c for c in calls)
    assert result == items


def test_get_items_with_missing_invalid_mode(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "invalid")
    assert result is None


def test_get_items_with_missing_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.get_items_with_missing("http://eros:6969", "key", 30, False, "movie")
    assert result is None


# ── get_cutoff_unmet_items ────────────────────────────────────────────────────

def test_get_cutoff_unmet_items_returns_records(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 1, "monitored": True}, {"id": 2, "monitored": True}]}
    with patch.object(eros_api, "arr_request", return_value=payload):
        result = eros_api.get_cutoff_unmet_items("http://eros:6969", "key", 30, False)
    assert len(result) == 2


def test_get_cutoff_unmet_items_filters_monitored(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 1, "monitored": True}, {"id": 2, "monitored": False}]}
    with patch.object(eros_api, "arr_request", return_value=payload):
        result = eros_api.get_cutoff_unmet_items("http://eros:6969", "key", 30, True)
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_get_cutoff_unmet_items_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.get_cutoff_unmet_items("http://eros:6969", "key", 30, False)
    assert result is None


# ── get_quality_upgrades ──────────────────────────────────────────────────────

def test_get_quality_upgrades_movie_mode(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    items = [
        {"id": 1, "hasFile": True, "qualityCutoffNotMet": True, "monitored": True},
        {"id": 2, "hasFile": False, "qualityCutoffNotMet": True, "monitored": True},
    ]
    with patch.object(eros_api, "arr_request", return_value=items):
        result = eros_api.get_quality_upgrades("http://eros:6969", "key", 30, False, "movie")
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_get_quality_upgrades_scene_mode(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    payload = {"records": [{"id": 10, "monitored": True}]}
    with patch.object(eros_api, "arr_request", return_value=payload):
        result = eros_api.get_quality_upgrades("http://eros:6969", "key", 30, False, "scene")
    assert result == [{"id": 10, "monitored": True}]


def test_get_quality_upgrades_scene_fallback_to_movie(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    items = [{"id": 5, "hasFile": True, "qualityCutoffNotMet": True, "monitored": True}]
    calls = []
    def mock_arr(url, key, timeout, endpoint, **kwargs):
        calls.append(endpoint)
        if "scene" in endpoint:
            return None
        return items
    with patch.object(eros_api, "arr_request", side_effect=mock_arr):
        result = eros_api.get_quality_upgrades("http://eros:6969", "key", 30, False, "scene")
    assert result == items


def test_get_quality_upgrades_invalid_mode(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.get_quality_upgrades("http://eros:6969", "key", 30, False, "bad")
    assert result is None


# ── item_search ───────────────────────────────────────────────────────────────

def test_item_search_returns_command_id(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value={"id": 99}):
        result = eros_api.item_search("http://eros:6969", "key", 30, [1, 2])
    assert result == 99


def test_item_search_returns_none_for_empty_ids(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.item_search("http://eros:6969", "key", 30, [])
    assert result is None


def test_item_search_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.item_search("http://eros:6969", "key", 30, [1])
    assert result is None


# ── get_command_status ────────────────────────────────────────────────────────

def test_get_command_status_returns_status(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value={"id": 5, "status": "completed"}):
        result = eros_api.get_command_status("http://eros:6969", "key", 30, 5)
    assert result["status"] == "completed"


def test_get_command_status_returns_none_for_missing_id(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    result = eros_api.get_command_status("http://eros:6969", "key", 30, None)
    assert result is None


def test_get_command_status_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.get_command_status("http://eros:6969", "key", 30, 5)
    assert result is None


# ── check_connection ──────────────────────────────────────────────────────────

def test_check_connection_returns_true_on_success(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value={"version": "3.0.0.1234"}):
        result = eros_api.check_connection("http://eros:6969", "key", 30)
    assert result is True


def test_check_connection_ssl_setting_passed_through(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(eros_api.session, "get", side_effect=_capture_session_get({"version": "3.0"}, captured)):
        eros_api.check_connection("http://eros:6969", "key", 30)
    assert captured.get("verify") is False


def test_check_connection_returns_false_when_no_version(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value={"version": None}):
        result = eros_api.check_connection("http://eros:6969", "key", 30)
    assert result is False


def test_check_connection_returns_false_on_failure(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", return_value=None):
        result = eros_api.check_connection("http://eros:6969", "key", 30)
    assert result is False


def test_check_connection_returns_false_on_exception(monkeypatch):
    monkeypatch.setattr("src.primary.apps.eros.api.get_ssl_verify_setting", lambda: True)
    with patch.object(eros_api, "arr_request", side_effect=Exception("boom")):
        result = eros_api.check_connection("http://eros:6969", "key", 30)
    assert result is False

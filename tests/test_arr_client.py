"""Tests for src/primary/utils/arr_client.py — the shared *Arr HTTP client."""
from unittest.mock import MagicMock, patch

import requests as _requests

import src.primary.utils.arr_client as arr_client


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data, status_code=200, content=None):
    mock = MagicMock()
    mock.status_code = status_code
    if content is not None:
        mock.content = content
        mock.text = content if isinstance(content, str) else content.decode()
    else:
        mock.content = str(json_data).encode() if json_data is not None else b""
        mock.text = mock.content.decode() if mock.content else ""
    if json_data is not None:
        mock.json.return_value = json_data
    else:
        import json as _json
        mock.json.side_effect = _json.JSONDecodeError("no json", "", 0)
    if status_code >= 400:
        def _raise():
            raise _requests.exceptions.HTTPError(f"{status_code} Error")
        mock.raise_for_status.side_effect = _raise
    else:
        mock.raise_for_status.return_value = None
    return mock


# ── get_version / get_user_agent ─────────────────────────────────────────────

def test_get_version_reads_version_txt(tmp_path, monkeypatch):
    (tmp_path / "version.txt").write_text("7.4.1\n")
    monkeypatch.setattr(arr_client, "_PROJECT_ROOT", str(tmp_path))
    assert arr_client.get_version() == "7.4.1"


def test_get_version_falls_back_to_dev_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(arr_client, "_PROJECT_ROOT", str(tmp_path))
    assert arr_client.get_version() == "dev"


def test_get_version_falls_back_to_dev_when_empty(tmp_path, monkeypatch):
    (tmp_path / "version.txt").write_text("   \n")
    monkeypatch.setattr(arr_client, "_PROJECT_ROOT", str(tmp_path))
    assert arr_client.get_version() == "dev"


def test_get_user_agent_uses_running_version(tmp_path, monkeypatch):
    (tmp_path / "version.txt").write_text("7.4.1\n")
    monkeypatch.setattr(arr_client, "_PROJECT_ROOT", str(tmp_path))
    assert arr_client.get_user_agent() == "Seekarr/7.4.1 (https://github.com/diybits/seekarr)"


# ── arr_request — URL construction and headers ───────────────────────────────

def _capture_get(json_data, captured):
    def _get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _get


def test_arr_request_defaults_to_v3_prefix(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"ok": True}, captured)):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "system/status")
    assert result == {"ok": True}
    assert captured["url"] == "http://sonarr:8989/api/v3/system/status"


def test_arr_request_supports_v1_prefix(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"ok": True}, captured)):
        arr_client.arr_request("lidarr", "http://lidarr:8686", "key", 30, "system/status", api_prefix="v1")
    assert captured["url"] == "http://lidarr:8686/api/v1/system/status"


def test_arr_request_strips_ending_slash_and_leading_slash_on_endpoint(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"ok": True}, captured)):
        arr_client.arr_request("radarr", "http://radarr:7878/", "key", 30, "/movie")
    assert captured["url"] == "http://radarr:7878/api/v3/movie"


def test_arr_request_sends_api_key_and_user_agent(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    monkeypatch.setattr(arr_client, "get_version", lambda: "7.4.1")
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"ok": True}, captured)):
        arr_client.arr_request("sonarr", "http://sonarr:8989", "secret", 30, "system/status")
    assert captured["headers"]["X-Api-Key"] == "secret"
    assert captured["headers"]["User-Agent"] == "Seekarr/7.4.1 (https://github.com/diybits/seekarr)"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_arr_request_respects_ssl_setting(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: False)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"ok": True}, captured)):
        arr_client.arr_request("sonarr", "https://sonarr:8989", "key", 30, "system/status")
    assert captured["verify"] is False


# ── arr_request — method dispatch ────────────────────────────────────────────

def _capture_method(method_name, json_data, captured):
    def _call(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _mock_response(json_data)
    return _call


def test_arr_request_get_sends_params(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"records": []}, captured)):
        arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "queue",
                               params={"page": 1, "pageSize": 10})
    assert captured["params"] == {"page": 1, "pageSize": 10}


def test_arr_request_post_sends_json_body(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "post", side_effect=_capture_method("post", {"id": 42}, captured)):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "command",
                                        method="POST", data={"name": "SendCalibration"})
    assert result == {"id": 42}
    assert captured["json"] == {"name": "SendCalibration"}


def test_arr_request_put_sends_json_body(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "put", side_effect=_capture_method("put", {"id": 1}, captured)):
        arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "series/1",
                               method="PUT", data={"monitored": False})
    assert captured["json"] == {"monitored": False}


def test_arr_request_delete_sends_no_body(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "delete", side_effect=_capture_method("delete", None, captured)):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "queue/5", method="DELETE")
    assert "json" not in captured or captured.get("json") is None
    assert result == {}


def test_arr_request_unsupported_method_returns_none(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "queue", method="PATCH")
    assert result is None


# ── arr_request — response handling ──────────────────────────────────────────

def test_arr_request_returns_parsed_json(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    captured = {}
    with patch.object(arr_client.session, "get", side_effect=_capture_get({"version": "v4"}, captured)):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "system/status")
    assert result == {"version": "v4"}


def test_arr_request_returns_empty_dict_for_empty_content(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    def _get(url, **kwargs):
        return _mock_response(None, status_code=200, content=b"")
    with patch.object(arr_client.session, "get", side_effect=_get):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "queue/5", method="GET")
    assert result == {}


def test_arr_request_returns_none_for_invalid_json(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    def _get(url, **kwargs):
        return _mock_response(None, status_code=200, content=b"<html>not json</html>")
    with patch.object(arr_client.session, "get", side_effect=_get):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "system/status")
    assert result is None


def test_arr_request_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    def _get(url, **kwargs):
        return _mock_response(None, status_code=404, content=b"not found")
    with patch.object(arr_client.session, "get", side_effect=_get):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "nope")
    assert result is None


def test_arr_request_returns_none_on_connection_error(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    with patch.object(arr_client.session, "get", side_effect=_requests.exceptions.ConnectionError("boom")):
        result = arr_client.arr_request("sonarr", "http://sonarr:8989", "key", 30, "system/status")
    assert result is None


# ── arr_request — validation ─────────────────────────────────────────────────

def test_arr_request_returns_none_for_missing_credentials(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    assert arr_client.arr_request("sonarr", "", "key", 30, "system/status") is None
    assert arr_client.arr_request("sonarr", "http://sonarr:8989", "", 30, "system/status") is None


def test_arr_request_returns_none_for_invalid_scheme(monkeypatch):
    monkeypatch.setattr("src.primary.utils.arr_client.get_ssl_verify_setting", lambda: True)
    result = arr_client.arr_request("sonarr", "sonarr:8989", "key", 30, "system/status")
    assert result is None

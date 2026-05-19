"""Tests for src/primary/apps/sonarr_routes.py — POST /test-connection.

sonarr_routes is representative of all app _routes blueprints, which share
the same test-connection pattern (input validation → socket check → HTTP call).
"""
import socket
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

import src.primary.apps.sonarr_routes as sr

# ── Minimal Flask app ─────────────────────────────────────────────────────────

_test_app = Flask(__name__)
_test_app.config["TESTING"] = True
_test_app.register_blueprint(sr.sonarr_bp, url_prefix="/api/sonarr")


@pytest.fixture
def client():
    with _test_app.test_client() as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_PAYLOAD = {"api_url": "http://sonarr:8989", "api_key": "abc123"}


def _mock_socket(connect_result=0):
    """Return a mock socket whose connect_ex returns connect_result."""
    sock = MagicMock()
    sock.connect_ex.return_value = connect_result
    return sock


def _mock_response(status_code=200, json_data=None):
    """Return a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {"version": "4.0.0"}
    resp.raise_for_status.return_value = None
    return resp


# ── Input validation ──────────────────────────────────────────────────────────

def test_missing_api_url_returns_400(client):
    resp = client.post("/api/sonarr/test-connection", json={"api_key": "abc"})
    assert resp.status_code == 400


def test_missing_api_key_returns_400(client):
    resp = client.post("/api/sonarr/test-connection", json={"api_url": "http://sonarr:8989"})
    assert resp.status_code == 400


def test_missing_both_returns_400(client):
    resp = client.post("/api/sonarr/test-connection", json={})
    assert resp.status_code == 400


def test_url_without_scheme_returns_400(client):
    resp = client.post("/api/sonarr/test-connection",
                       json={"api_url": "sonarr:8989", "api_key": "abc"})
    assert resp.status_code == 400


def test_url_with_http_scheme_passes_validation(client):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value.__enter__ = lambda s: _mock_socket(0)
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.return_value = _mock_response(200)
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 200


def test_url_with_https_scheme_passes_validation(client):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.return_value = _mock_response(200)
        resp = client.post("/api/sonarr/test-connection",
                           json={"api_url": "https://sonarr:8989", "api_key": "abc"})
    assert resp.status_code == 200


# ── Socket connectivity check ─────────────────────────────────────────────────

def test_socket_connection_refused_returns_404(client):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls:
        mock_sock_cls.return_value = _mock_socket(connect_result=111)
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 404


def test_socket_dns_failure_returns_404(client):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls:
        instance = _mock_socket()
        instance.connect_ex.side_effect = socket.gaierror("name not known")
        mock_sock_cls.return_value = instance
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 404


def test_socket_error_message_mentions_host(client):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls:
        instance = _mock_socket()
        instance.connect_ex.side_effect = socket.gaierror("name not known")
        mock_sock_cls.return_value = instance
        data = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD).get_json()
    assert "sonarr" in data["message"].lower() or "dns" in data["message"].lower()


# ── HTTP response mapping ─────────────────────────────────────────────────────

def _post_with_mock_http(client, status_code, json_data=None):
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.return_value = _mock_response(status_code, json_data)
        return client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)


def test_http_401_returns_401(client):
    assert _post_with_mock_http(client, 401).status_code == 401


def test_http_403_returns_403(client):
    assert _post_with_mock_http(client, 403).status_code == 403


def test_http_404_returns_404(client):
    assert _post_with_mock_http(client, 404).status_code == 404


def test_http_500_returns_500(client):
    assert _post_with_mock_http(client, 500).status_code == 500


def test_http_200_returns_success_true(client):
    resp = _post_with_mock_http(client, 200, {"version": "4.0.0"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_http_200_includes_version(client):
    resp = _post_with_mock_http(client, 200, {"version": "4.1.2"})
    assert resp.get_json()["version"] == "4.1.2"


# ── Network exception handling ────────────────────────────────────────────────

def test_timeout_returns_504(client):
    import requests as _requests
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.side_effect = _requests.exceptions.Timeout()
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 504


def test_connection_error_returns_404(client):
    import requests as _requests
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.side_effect = _requests.exceptions.ConnectionError("Connection refused")
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 404


def test_request_exception_returns_500(client):
    import requests as _requests
    with patch("src.primary.utils.connection_test.socket.socket") as mock_sock_cls, \
         patch("src.primary.utils.connection_test.requests.get") as mock_get, \
         patch("src.primary.utils.connection_test.get_ssl_verify_setting", return_value=True):
        mock_sock_cls.return_value = _mock_socket(0)
        mock_get.side_effect = _requests.exceptions.RequestException("unexpected")
        resp = client.post("/api/sonarr/test-connection", json=VALID_PAYLOAD)
    assert resp.status_code == 500

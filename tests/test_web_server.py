"""Flask route smoke tests for src/primary/web_server.py.

Covers: health check, version, unauthenticated 401s, authenticated API responses,
login flow, invalid app names, settings shape, and setup redirect.
"""
import os
import sys

# web_server.py uses `from primary.utils.logger import ...` (no src. prefix),
# so src/ must be on sys.path before the import.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# SECRET_KEY must be set before web_server is imported to avoid /config/secret_key I/O
os.environ.setdefault("SECRET_KEY", "test-secret-key-web-server-smoke")

import json
import pytest

import src.primary.auth as _auth
import src.primary.web_server as ws

_app = ws.app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Test client with authenticate_request bypassed — tests route shapes."""
    _app.config["TESTING"] = True
    saved = list(_app.before_request_funcs.get(None, []))
    _app.before_request_funcs[None] = []
    try:
        with _app.test_client() as c:
            yield c
    finally:
        _app.before_request_funcs[None] = saved


@pytest.fixture
def unauthed_client(config_dir):
    """Test client with a real user but no active session — tests 401 behaviour."""
    _app.config["TESTING"] = True
    _auth.create_user("testuser", "TestPass1!")
    with _app.test_client() as c:
        yield c


@pytest.fixture
def authed_client(config_dir):
    """Test client that logs in via POST /login — tests protected route responses."""
    _app.config["TESTING"] = True
    _auth.create_user("testuser", "TestPass1!")
    with _app.test_client() as c:
        resp = c.post("/login", json={"username": "testuser", "password": "TestPass1!"})
        assert resp.status_code == 200, f"Login failed during fixture setup: {resp.data}"
        yield c


# ── /ping ─────────────────────────────────────────────────────────────────────

def test_ping_returns_status_ok(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "OK"}


def test_ping_content_type_is_json(client):
    resp = client.get("/ping")
    assert "application/json" in resp.content_type


# ── /version.txt ──────────────────────────────────────────────────────────────

def test_version_txt_returns_200(client):
    resp = client.get("/version.txt")
    assert resp.status_code == 200


def test_version_txt_is_not_empty(client):
    resp = client.get("/version.txt")
    assert len(resp.data.strip()) > 0


# ── unauthenticated API → 401 ─────────────────────────────────────────────────

def test_api_settings_unauthenticated_returns_401(unauthed_client):
    resp = unauthed_client.get("/api/settings/sonarr")
    assert resp.status_code == 401


def test_api_configured_apps_unauthenticated_returns_401(unauthed_client):
    resp = unauthed_client.get("/api/configured-apps")
    assert resp.status_code == 401


def test_api_stats_unauthenticated_returns_401(unauthed_client):
    resp = unauthed_client.get("/api/stats")
    assert resp.status_code == 401


def test_api_status_unauthenticated_returns_401(unauthed_client):
    resp = unauthed_client.get("/api/status/sonarr")
    assert resp.status_code == 401


# ── /login ────────────────────────────────────────────────────────────────────

def test_login_post_missing_credentials_returns_400(unauthed_client):
    resp = unauthed_client.post("/login", json={"username": "testuser"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_login_post_wrong_password_returns_401(unauthed_client):
    resp = unauthed_client.post(
        "/login", json={"username": "testuser", "password": "WrongPass99!"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_login_post_success_returns_200(unauthed_client):
    resp = unauthed_client.post(
        "/login", json={"username": "testuser", "password": "TestPass1!"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_login_post_success_sets_session_cookie(unauthed_client):
    resp = unauthed_client.post(
        "/login", json={"username": "testuser", "password": "TestPass1!"}
    )
    assert _auth.SESSION_COOKIE_NAME in resp.headers.get("Set-Cookie", "")


# ── /setup ────────────────────────────────────────────────────────────────────

def test_setup_get_when_no_user_returns_200(client):
    resp = client.get("/setup")
    assert resp.status_code == 200


def test_setup_redirects_to_login_when_user_exists(config_dir):
    _auth.create_user("testuser", "TestPass1!")
    _app.config["TESTING"] = True
    with _app.test_client() as c:
        resp = c.get("/setup")
    assert resp.status_code == 302
    assert "/login" in resp.location


# ── /api/configured-apps ─────────────────────────────────────────────────────

def test_configured_apps_returns_all_known_apps(client):
    resp = client.get("/api/configured-apps")
    assert resp.status_code == 200
    data = resp.get_json()
    for app_name in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        assert app_name in data


def test_configured_apps_values_are_booleans(client):
    resp = client.get("/api/configured-apps")
    data = resp.get_json()
    assert all(isinstance(v, bool) for v in data.values())


# ── /api/status/<app_name> ────────────────────────────────────────────────────

def test_status_invalid_app_returns_400(client):
    resp = client.get("/api/status/unknownapp")
    assert resp.status_code == 400


def test_status_valid_app_returns_200(client):
    resp = client.get("/api/status/sonarr")
    assert resp.status_code == 200


def test_status_response_has_count_keys(client):
    # Multi-instance apps return total_configured / connected_count
    resp = client.get("/api/status/sonarr")
    data = resp.get_json()
    assert "total_configured" in data or "configured" in data


# ── /api/settings/<app_name> ─────────────────────────────────────────────────

def test_settings_invalid_app_returns_400(client):
    resp = client.get("/api/settings/DOESNOTEXIST")
    assert resp.status_code == 400


def test_settings_valid_app_returns_json(client):
    resp = client.get("/api/settings/sonarr")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None


# ── authenticated access after login ─────────────────────────────────────────

def test_authenticated_configured_apps_returns_200(authed_client):
    resp = authed_client.get("/api/configured-apps")
    assert resp.status_code == 200


def test_authenticated_ping_returns_200(authed_client):
    resp = authed_client.get("/ping")
    assert resp.status_code == 200


def test_authenticated_stats_returns_success(authed_client):
    resp = authed_client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True


def test_authenticated_settings_sonarr_returns_200(authed_client):
    resp = authed_client.get("/api/settings/sonarr")
    assert resp.status_code == 200

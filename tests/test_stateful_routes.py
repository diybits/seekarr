"""Tests for src/primary/stateful_routes.py — info, reset, update-expiration endpoints."""
import json
from unittest.mock import patch

import pytest
from flask import Flask

import src.primary.stateful_routes as sr

# ── Minimal Flask app ─────────────────────────────────────────────────────────

_test_app = Flask(__name__)
_test_app.config["TESTING"] = True
_test_app.register_blueprint(sr.stateful_api, url_prefix="/api/stateful")


@pytest.fixture
def client():
    with _test_app.test_client() as c:
        yield c


# ── GET /api/stateful/info ────────────────────────────────────────────────────

def test_info_returns_success_true(client):
    info = {"created_at_ts": 1000, "expires_at_ts": 2000, "interval_hours": 168}
    with patch("src.primary.stateful_routes.get_stateful_management_info", return_value=info):
        data = json.loads(client.get("/api/stateful/info").data)
    assert data["success"] is True


def test_info_returns_all_fields(client):
    info = {"created_at_ts": 1000, "expires_at_ts": 2000, "interval_hours": 168}
    with patch("src.primary.stateful_routes.get_stateful_management_info", return_value=info):
        data = json.loads(client.get("/api/stateful/info").data)
    assert data["created_at_ts"] == 1000
    assert data["expires_at_ts"] == 2000
    assert data["interval_hours"] == 168


def test_info_has_cors_header(client):
    with patch("src.primary.stateful_routes.get_stateful_management_info", return_value={}):
        resp = client.get("/api/stateful/info")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


def test_info_exception_returns_500(client):
    with patch("src.primary.stateful_routes.get_stateful_management_info",
               side_effect=RuntimeError("boom")):
        resp = client.get("/api/stateful/info")
    assert resp.status_code == 500


# ── POST /api/stateful/reset ──────────────────────────────────────────────────

def test_reset_success_returns_200(client):
    with patch("src.primary.stateful_routes.reset_stateful_management", return_value=True):
        resp = client.post("/api/stateful/reset")
    assert resp.status_code == 200
    assert json.loads(resp.data)["success"] is True


def test_reset_failure_returns_500(client):
    with patch("src.primary.stateful_routes.reset_stateful_management", return_value=False):
        resp = client.post("/api/stateful/reset")
    assert resp.status_code == 500
    assert json.loads(resp.data)["success"] is False


def test_reset_exception_returns_500(client):
    with patch("src.primary.stateful_routes.reset_stateful_management",
               side_effect=RuntimeError("disk error")):
        resp = client.post("/api/stateful/reset")
    assert resp.status_code == 500


def test_reset_has_cors_header(client):
    with patch("src.primary.stateful_routes.reset_stateful_management", return_value=True):
        resp = client.post("/api/stateful/reset")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ── POST /api/stateful/update-expiration ──────────────────────────────────────

def test_update_expiration_success_returns_200(client):
    info = {"expires_at": 9999, "expires_date": "2026-01-01"}
    with patch("src.primary.stateful_routes.update_lock_expiration", return_value=True), \
         patch("src.primary.stateful_routes.get_stateful_management_info", return_value=info):
        resp = client.post("/api/stateful/update-expiration", json={"hours": 48})
    assert resp.status_code == 200
    assert json.loads(resp.data)["success"] is True


def test_update_expiration_missing_hours_returns_400(client):
    resp = client.post("/api/stateful/update-expiration", json={})
    assert resp.status_code == 400


def test_update_expiration_zero_hours_returns_400(client):
    resp = client.post("/api/stateful/update-expiration", json={"hours": 0})
    assert resp.status_code == 400


def test_update_expiration_negative_hours_returns_400(client):
    resp = client.post("/api/stateful/update-expiration", json={"hours": -10})
    assert resp.status_code == 400


def test_update_expiration_non_integer_hours_returns_400(client):
    resp = client.post("/api/stateful/update-expiration", json={"hours": "48"})
    assert resp.status_code == 400


def test_update_expiration_failure_returns_500(client):
    with patch("src.primary.stateful_routes.update_lock_expiration", return_value=False):
        resp = client.post("/api/stateful/update-expiration", json={"hours": 24})
    assert resp.status_code == 500


def test_update_expiration_has_cors_header(client):
    info = {}
    with patch("src.primary.stateful_routes.update_lock_expiration", return_value=True), \
         patch("src.primary.stateful_routes.get_stateful_management_info", return_value=info):
        resp = client.post("/api/stateful/update-expiration", json={"hours": 24})
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"

"""Tests for src/primary/routes/history_routes.py — GET and DELETE endpoints."""
import json
from unittest.mock import patch

import pytest
from flask import Flask

import src.primary.routes.history_routes as hr

# ── Minimal Flask app ─────────────────────────────────────────────────────────

_test_app = Flask(__name__)
_test_app.config["TESTING"] = True
_test_app.register_blueprint(hr.history_blueprint, url_prefix="/api/history")


@pytest.fixture
def client():
    with _test_app.test_client() as c:
        yield c


_DEFAULT_RESULT = {"entries": [], "total_entries": 0, "total_pages": 1, "current_page": 1}


# ── GET /api/history/<app_type> ───────────────────────────────────────────────

def test_get_valid_app_returns_200(client):
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT):
        resp = client.get("/api/history/sonarr")
    assert resp.status_code == 200


def test_get_all_returns_200(client):
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT):
        resp = client.get("/api/history/all")
    assert resp.status_code == 200


def test_get_invalid_app_returns_400(client):
    resp = client.get("/api/history/unknownapp")
    assert resp.status_code == 400


def test_get_passes_search_query(client):
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT) as mock:
        client.get("/api/history/sonarr?search=breaking")
    mock.assert_called_once_with("sonarr", "breaking", 1, 20)


def test_get_passes_pagination_params(client):
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT) as mock:
        client.get("/api/history/sonarr?page=2&page_size=50")
    mock.assert_called_once_with("sonarr", "", 2, 50)


def test_get_disallowed_page_size_defaults_to_20(client):
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT) as mock:
        client.get("/api/history/sonarr?page_size=7")
    mock.assert_called_once_with("sonarr", "", 1, 20)


def test_get_returns_result_from_history_manager(client):
    result = {"entries": [{"id": 1}], "total_entries": 1, "total_pages": 1, "current_page": 1}
    with patch("src.primary.routes.history_routes.get_history", return_value=result):
        data = json.loads(client.get("/api/history/sonarr").data)
    assert data["total_entries"] == 1
    assert len(data["entries"]) == 1


def test_get_all_valid_app_types_return_200(client):
    valid = ["all", "sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr"]
    with patch("src.primary.routes.history_routes.get_history", return_value=_DEFAULT_RESULT):
        for app in valid:
            resp = client.get(f"/api/history/{app}")
            assert resp.status_code == 200, f"{app} should return 200"


def test_get_exception_returns_500(client):
    with patch("src.primary.routes.history_routes.get_history",
               side_effect=RuntimeError("disk error")):
        resp = client.get("/api/history/sonarr")
    assert resp.status_code == 500


# ── DELETE /api/history/<app_type> ────────────────────────────────────────────

def test_delete_valid_app_returns_200(client):
    with patch("src.primary.routes.history_routes.clear_history", return_value=True):
        resp = client.delete("/api/history/sonarr")
    assert resp.status_code == 200


def test_delete_invalid_app_returns_400(client):
    resp = client.delete("/api/history/unknownapp")
    assert resp.status_code == 400


def test_delete_all_returns_200(client):
    with patch("src.primary.routes.history_routes.clear_history", return_value=True):
        resp = client.delete("/api/history/all")
    assert resp.status_code == 200


def test_delete_failure_returns_500(client):
    with patch("src.primary.routes.history_routes.clear_history", return_value=False):
        resp = client.delete("/api/history/sonarr")
    assert resp.status_code == 500


def test_delete_exception_returns_500(client):
    with patch("src.primary.routes.history_routes.clear_history",
               side_effect=RuntimeError("io error")):
        resp = client.delete("/api/history/sonarr")
    assert resp.status_code == 500


def test_delete_response_includes_message(client):
    with patch("src.primary.routes.history_routes.clear_history", return_value=True):
        data = json.loads(client.delete("/api/history/radarr").data)
    assert "message" in data

"""Tests for src/primary/apps/swaparr_routes.py — status, settings, reset endpoints."""
import json
import os
from unittest.mock import patch

import pytest
from flask import Flask

import src.primary.apps.swaparr_routes as sr

# ── Minimal Flask app ─────────────────────────────────────────────────────────

_test_app = Flask(__name__)
_test_app.config["TESTING"] = True
_test_app.register_blueprint(sr.swaparr_bp, url_prefix="/api/swaparr")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with CONFIG_DIR redirected to tmp_path."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    with _test_app.test_client() as c:
        yield c, tmp_path


def _write_strikes(base, app_name, data):
    """Write a strikes.json file under base/swaparr/<app_name>/."""
    app_dir = base / "swaparr" / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "strikes.json").write_text(json.dumps(data))


# ── GET /api/swaparr/status ───────────────────────────────────────────────────

def test_status_returns_200(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        resp = c.get("/api/swaparr/status")
    assert resp.status_code == 200


def test_status_includes_enabled_field(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={"enabled": True}):
        data = c.get("/api/swaparr/status").get_json()
    assert data["enabled"] is True


def test_status_no_state_dir_returns_empty_statistics(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        data = c.get("/api/swaparr/status").get_json()
    assert data["statistics"] == {}


def test_status_aggregates_strike_counts(client):
    c, base = client
    _write_strikes(base, "sonarr", {
        "item1": {"strikes": 2, "removed": False},
        "item2": {"strikes": 0, "removed": True},
    })
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        data = c.get("/api/swaparr/status").get_json()
    assert data["statistics"]["sonarr"]["total_tracked"] == 2
    assert data["statistics"]["sonarr"]["currently_striked"] == 1
    assert data["statistics"]["sonarr"]["removed"] == 1


def test_status_multiple_apps_all_aggregated(client):
    c, base = client
    _write_strikes(base, "sonarr", {"a": {"strikes": 1, "removed": False}})
    _write_strikes(base, "radarr", {"b": {"strikes": 0, "removed": False}})
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        data = c.get("/api/swaparr/status").get_json()
    assert "sonarr" in data["statistics"]
    assert "radarr" in data["statistics"]


def test_status_corrupt_strike_file_returns_error_entry(client):
    c, base = client
    app_dir = base / "swaparr" / "sonarr"
    app_dir.mkdir(parents=True)
    (app_dir / "strikes.json").write_text("not valid json {{{")
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        data = c.get("/api/swaparr/status").get_json()
    assert "error" in data["statistics"]["sonarr"]


def test_status_settings_section_has_defaults(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}):
        data = c.get("/api/swaparr/status").get_json()
    s = data["settings"]
    assert "max_strikes" in s
    assert "max_download_time" in s
    assert "dry_run" in s


# ── GET /api/swaparr/settings ─────────────────────────────────────────────────

def test_get_settings_returns_200(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={"enabled": False}):
        resp = c.get("/api/swaparr/settings")
    assert resp.status_code == 200


def test_get_settings_returns_loaded_settings(client):
    c, _ = client
    settings = {"enabled": True, "max_strikes": 5}
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value=settings):
        data = c.get("/api/swaparr/settings").get_json()
    assert data["max_strikes"] == 5


# ── POST /api/swaparr/settings ────────────────────────────────────────────────

def test_update_settings_no_body_returns_400(client):
    c, _ = client
    resp = c.post("/api/swaparr/settings", json=None,
                  content_type="application/json")
    assert resp.status_code == 400


def test_update_settings_success_returns_success_true(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}), \
         patch("src.primary.apps.swaparr_routes.save_settings", return_value=True):
        resp = c.post("/api/swaparr/settings", json={"max_strikes": 4})
    assert resp.get_json()["success"] is True


def test_update_settings_save_failure_returns_500(client):
    c, _ = client
    with patch("src.primary.apps.swaparr_routes.load_settings", return_value={}), \
         patch("src.primary.apps.swaparr_routes.save_settings", return_value=False):
        resp = c.post("/api/swaparr/settings", json={"max_strikes": 4})
    assert resp.status_code == 500


def test_update_settings_merges_with_existing(client):
    c, _ = client
    captured = {}
    def fake_save(app, settings):
        captured.update(settings)
        return True
    with patch("src.primary.apps.swaparr_routes.load_settings",
               return_value={"enabled": True, "max_strikes": 3}), \
         patch("src.primary.apps.swaparr_routes.save_settings", side_effect=fake_save):
        c.post("/api/swaparr/settings", json={"max_strikes": 7})
    assert captured["enabled"] is True
    assert captured["max_strikes"] == 7


# ── POST /api/swaparr/reset ───────────────────────────────────────────────────

def test_reset_no_state_dir_returns_success(client):
    c, _ = client
    resp = c.post("/api/swaparr/reset", json={})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_reset_all_removes_all_strike_files(client):
    c, base = client
    _write_strikes(base, "sonarr", {"a": {}})
    _write_strikes(base, "radarr", {"b": {}})
    c.post("/api/swaparr/reset", json={})
    assert not (base / "swaparr" / "sonarr" / "strikes.json").exists()
    assert not (base / "swaparr" / "radarr" / "strikes.json").exists()


def test_reset_specific_app_removes_only_that_file(client):
    c, base = client
    _write_strikes(base, "sonarr", {"a": {}})
    _write_strikes(base, "radarr", {"b": {}})
    c.post("/api/swaparr/reset", json={"app_name": "sonarr"})
    assert not (base / "swaparr" / "sonarr" / "strikes.json").exists()
    assert (base / "swaparr" / "radarr" / "strikes.json").exists()


def test_reset_specific_app_not_found_returns_404(client):
    c, base = client
    (base / "swaparr").mkdir(parents=True)
    resp = c.post("/api/swaparr/reset", json={"app_name": "lidarr"})
    assert resp.status_code == 404

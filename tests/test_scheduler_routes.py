"""Tests for src/primary/routes/scheduler_routes.py — load, save, history endpoints."""
import json
import os
from unittest.mock import patch

import pytest
from flask import Flask

import src.primary.routes.scheduler_routes as sr

# ── Minimal Flask app for blueprint isolation ─────────────────────────────────

_test_app = Flask(__name__)
_test_app.config["TESTING"] = True
_test_app.register_blueprint(sr.scheduler_api)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with CONFIG_DIR and SCHEDULE_FILE redirected to tmp_path."""
    cfg = tmp_path / "scheduler"
    cfg.mkdir()
    schedule = cfg / "schedule.json"
    monkeypatch.setattr(sr, "CONFIG_DIR", str(cfg))
    monkeypatch.setattr(sr, "SCHEDULE_FILE", str(schedule))
    with _test_app.test_client() as c:
        yield c, schedule


# ── GET /api/scheduler/load ───────────────────────────────────────────────────

def test_load_no_file_returns_default_keys(client):
    c, _ = client
    resp = c.get("/api/scheduler/load")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    for key in ["global", "sonarr", "radarr", "lidarr", "readarr"]:
        assert key in data


def test_load_no_file_returns_empty_lists(client):
    c, _ = client
    data = json.loads(c.get("/api/scheduler/load").data)
    assert all(v == [] for v in data.values())


def test_load_valid_file_returns_stored_entries(client):
    c, schedule = client
    stored = {"sonarr": [{"id": "s1", "action": "disable"}], "global": []}
    schedule.write_text(json.dumps(stored))
    data = json.loads(c.get("/api/scheduler/load").data)
    assert data["sonarr"] == [{"id": "s1", "action": "disable"}]


def test_load_merges_file_with_default_keys(client):
    c, schedule = client
    schedule.write_text(json.dumps({"sonarr": []}))
    data = json.loads(c.get("/api/scheduler/load").data)
    # radarr etc. should still be present from the default structure
    assert "radarr" in data


def test_load_preserves_extra_keys_from_file(client):
    c, schedule = client
    schedule.write_text(json.dumps({"whisparr": [{"id": "w1"}], "global": []}))
    data = json.loads(c.get("/api/scheduler/load").data)
    assert "whisparr" in data
    assert data["whisparr"] == [{"id": "w1"}]


def test_load_corrupt_file_returns_500(client):
    c, schedule = client
    schedule.write_text("not valid json {{{")
    resp = c.get("/api/scheduler/load")
    assert resp.status_code == 500


def test_load_response_has_cors_header(client):
    c, _ = client
    resp = c.get("/api/scheduler/load")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ── POST /api/scheduler/save ──────────────────────────────────────────────────

def test_save_valid_data_returns_success(client):
    c, _ = client
    resp = c.post("/api/scheduler/save",
                  json={"sonarr": [{"id": "s1", "action": "disable"}], "global": []})
    assert resp.status_code == 200
    assert json.loads(resp.data)["success"] is True


def test_save_persists_to_disk(client):
    c, schedule = client
    payload = {"sonarr": [{"id": "s1"}], "global": []}
    c.post("/api/scheduler/save", json=payload)
    assert schedule.exists()
    assert json.loads(schedule.read_text())["sonarr"] == [{"id": "s1"}]


def test_save_response_includes_timestamp(client):
    c, _ = client
    resp = c.post("/api/scheduler/save", json={"global": []})
    data = json.loads(resp.data)
    assert "timestamp" in data


def test_save_empty_dict_returns_400(client):
    c, _ = client
    resp = c.post("/api/scheduler/save", json={})
    assert resp.status_code == 400


def test_save_non_dict_body_returns_400(client):
    c, _ = client
    resp = c.post("/api/scheduler/save", json=["not", "a", "dict"])
    assert resp.status_code == 400


def test_save_creates_config_dir_if_missing(tmp_path, monkeypatch):
    cfg = tmp_path / "new_scheduler_dir"
    schedule = cfg / "schedule.json"
    monkeypatch.setattr(sr, "CONFIG_DIR", str(cfg))
    monkeypatch.setattr(sr, "SCHEDULE_FILE", str(schedule))
    with _test_app.test_client() as c:
        resp = c.post("/api/scheduler/save", json={"global": []})
    assert resp.status_code == 200
    assert cfg.exists()


def test_save_overwrites_existing_file(client):
    c, schedule = client
    schedule.write_text(json.dumps({"sonarr": [{"id": "old"}]}))
    c.post("/api/scheduler/save", json={"sonarr": [{"id": "new"}], "global": []})
    assert json.loads(schedule.read_text())["sonarr"] == [{"id": "new"}]


def test_save_response_has_cors_header(client):
    c, _ = client
    resp = c.post("/api/scheduler/save", json={"global": []})
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ── GET /api/scheduler/history ────────────────────────────────────────────────

def test_history_returns_success_true(client):
    c, _ = client
    with patch("src.primary.routes.scheduler_routes.get_execution_history", return_value=[]):
        data = json.loads(c.get("/api/scheduler/history").data)
    assert data["success"] is True


def test_history_returns_empty_list_when_no_executions(client):
    c, _ = client
    with patch("src.primary.routes.scheduler_routes.get_execution_history", return_value=[]):
        data = json.loads(c.get("/api/scheduler/history").data)
    assert data["history"] == []


def test_history_returns_entries_from_engine(client):
    c, _ = client
    entries = [{"id": "j1", "action": "disable", "status": "success"}]
    with patch("src.primary.routes.scheduler_routes.get_execution_history", return_value=entries):
        data = json.loads(c.get("/api/scheduler/history").data)
    assert data["history"] == entries


def test_history_response_includes_timestamp(client):
    c, _ = client
    with patch("src.primary.routes.scheduler_routes.get_execution_history", return_value=[]):
        data = json.loads(c.get("/api/scheduler/history").data)
    assert "timestamp" in data


def test_history_engine_exception_returns_500(client):
    c, _ = client
    with patch("src.primary.routes.scheduler_routes.get_execution_history",
               side_effect=RuntimeError("engine down")):
        resp = c.get("/api/scheduler/history")
    assert resp.status_code == 500


def test_history_response_has_cors_header(client):
    c, _ = client
    with patch("src.primary.routes.scheduler_routes.get_execution_history", return_value=[]):
        resp = c.get("/api/scheduler/history")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"

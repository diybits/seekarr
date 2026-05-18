"""Tests for src/primary/stateful_manager.py — lock file, processed IDs, expiration."""
import json
import time
from unittest.mock import patch

import pytest

import src.primary.stateful_manager as sm


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def stateful_dir(tmp_path, monkeypatch):
    """Per-test isolated stateful directory with lock file and app subdirs."""
    std = tmp_path / "stateful"
    std.mkdir()
    for app in sm.APP_TYPES:
        (std / app).mkdir()
    monkeypatch.setattr(sm, "STATEFUL_DIR", std)
    monkeypatch.setattr(sm, "LOCK_FILE", std / "lock.json")
    return std


# ── initialize_lock_file ──────────────────────────────────────────────────────

def test_initialize_lock_file_creates_file(stateful_dir):
    sm.initialize_lock_file()
    assert (stateful_dir / "lock.json").exists()


def test_initialize_lock_file_structure(stateful_dir):
    sm.initialize_lock_file()
    data = json.loads((stateful_dir / "lock.json").read_text())
    assert "created_at" in data
    assert "expires_at" in data
    assert data["expires_at"] > data["created_at"]


def test_initialize_lock_file_no_op_when_exists(stateful_dir):
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({"created_at": 999, "expires_at": 9999}))
    sm.initialize_lock_file()
    data = json.loads(lock.read_text())
    assert data["created_at"] == 999  # Not overwritten


# ── get_lock_info ─────────────────────────────────────────────────────────────

def test_get_lock_info_returns_dict_with_required_keys(stateful_dir):
    sm.initialize_lock_file()
    info = sm.get_lock_info()
    assert "created_at" in info
    assert "expires_at" in info


def test_get_lock_info_back_fills_missing_expires_at(stateful_dir):
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({"created_at": int(time.time())}))
    info = sm.get_lock_info()
    assert info["expires_at"] is not None
    assert info["expires_at"] > info["created_at"]


def test_get_lock_info_handles_corrupt_file_gracefully(stateful_dir):
    (stateful_dir / "lock.json").write_text("not valid json {{{")
    info = sm.get_lock_info()
    assert "created_at" in info
    assert "expires_at" in info


def test_get_lock_info_handles_missing_file_gracefully(stateful_dir):
    # No lock file — get_lock_info should call initialize_lock_file internally
    info = sm.get_lock_info()
    assert "created_at" in info
    assert "expires_at" in info


# ── update_lock_expiration ────────────────────────────────────────────────────

def test_update_lock_expiration_returns_true(stateful_dir):
    sm.initialize_lock_file()
    assert sm.update_lock_expiration(24) is True


def test_update_lock_expiration_uses_provided_hours(stateful_dir):
    sm.initialize_lock_file()
    info_before = sm.get_lock_info()
    sm.update_lock_expiration(10)
    info_after = sm.get_lock_info()
    expected = info_before["created_at"] + (10 * 3600)
    assert info_after["expires_at"] == expected


def test_update_lock_expiration_reads_setting_when_hours_none(stateful_dir):
    sm.initialize_lock_file()
    with patch("src.primary.stateful_manager.get_advanced_setting", return_value=48):
        sm.update_lock_expiration(None)
    info = sm.get_lock_info()
    created = info["created_at"]
    assert info["expires_at"] == created + (48 * 3600)


# ── reset_stateful_management ─────────────────────────────────────────────────

def test_reset_stateful_management_returns_true(stateful_dir):
    sm.initialize_lock_file()
    assert sm.reset_stateful_management() is True


def test_reset_stateful_management_creates_fresh_lock_file(stateful_dir):
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({"created_at": 1, "expires_at": 2}))
    sm.reset_stateful_management()
    data = json.loads(lock.read_text())
    assert data["created_at"] != 1
    assert data["expires_at"] > data["created_at"]


def test_reset_stateful_management_deletes_processed_id_files(stateful_dir):
    (stateful_dir / "sonarr" / "Default.json").write_text(
        json.dumps({"processed_ids": [1, 2, 3]})
    )
    (stateful_dir / "radarr" / "Instance1.json").write_text(
        json.dumps({"processed_ids": [4, 5]})
    )
    sm.reset_stateful_management()
    assert not (stateful_dir / "sonarr" / "Default.json").exists()
    assert not (stateful_dir / "radarr" / "Instance1.json").exists()


def test_reset_stateful_management_leaves_non_json_files(stateful_dir):
    txt = stateful_dir / "sonarr" / "notes.txt"
    txt.write_text("keep me")
    sm.reset_stateful_management()
    assert txt.exists()


# ── check_expiration ──────────────────────────────────────────────────────────

def test_check_expiration_returns_false_when_not_expired(stateful_dir):
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 3600,
    }))
    assert sm.check_expiration() is False


def test_check_expiration_returns_true_when_expired(stateful_dir):
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({
        "created_at": int(time.time()) - 7200,
        "expires_at": int(time.time()) - 1,
    }))
    assert sm.check_expiration() is True


def test_check_expiration_resets_when_expired(stateful_dir):
    (stateful_dir / "sonarr" / "Default.json").write_text(
        json.dumps({"processed_ids": [1, 2, 3]})
    )
    lock = stateful_dir / "lock.json"
    lock.write_text(json.dumps({
        "created_at": int(time.time()) - 7200,
        "expires_at": int(time.time()) - 1,
    }))
    sm.check_expiration()
    assert not (stateful_dir / "sonarr" / "Default.json").exists()


# ── get_processed_ids ─────────────────────────────────────────────────────────

def test_get_processed_ids_returns_empty_set_for_unknown_app(stateful_dir):
    assert sm.get_processed_ids("unknownapp", "Default") == set()


def test_get_processed_ids_returns_empty_set_when_no_file(stateful_dir):
    assert sm.get_processed_ids("sonarr", "Default") == set()


def test_get_processed_ids_returns_ids_from_file(stateful_dir):
    (stateful_dir / "sonarr" / "Default.json").write_text(
        json.dumps({"processed_ids": ["1", "2", "3"]})
    )
    result = sm.get_processed_ids("sonarr", "Default")
    assert result == {"1", "2", "3"}


def test_get_processed_ids_returns_empty_set_for_corrupt_file(stateful_dir):
    (stateful_dir / "sonarr" / "Default.json").write_text("not valid json")
    assert sm.get_processed_ids("sonarr", "Default") == set()


# ── add_processed_id ──────────────────────────────────────────────────────────

def test_add_processed_id_returns_false_for_unknown_app(stateful_dir):
    assert sm.add_processed_id("unknownapp", "Default", "42") is False


def test_add_processed_id_creates_file_and_adds_id(stateful_dir):
    assert sm.add_processed_id("sonarr", "Default", "42") is True
    ids = sm.get_processed_ids("sonarr", "Default")
    assert "42" in ids


def test_add_processed_id_accumulates_multiple_ids(stateful_dir):
    sm.add_processed_id("sonarr", "Default", "1")
    sm.add_processed_id("sonarr", "Default", "2")
    sm.add_processed_id("sonarr", "Default", "3")
    assert sm.get_processed_ids("sonarr", "Default") == {"1", "2", "3"}


def test_add_processed_id_no_duplicate_on_second_add(stateful_dir):
    sm.add_processed_id("sonarr", "Default", "99")
    sm.add_processed_id("sonarr", "Default", "99")
    ids = sm.get_processed_ids("sonarr", "Default")
    assert len([x for x in ids if x == "99"]) == 1


# ── is_processed ──────────────────────────────────────────────────────────────

def test_is_processed_returns_false_when_not_in_list(stateful_dir):
    assert sm.is_processed("sonarr", "Default", "42") is False


def test_is_processed_returns_true_after_add(stateful_dir):
    sm.add_processed_id("sonarr", "Default", "42")
    assert sm.is_processed("sonarr", "Default", "42") is True


def test_is_processed_coerces_int_id_to_string(stateful_dir):
    sm.add_processed_id("sonarr", "Default", "100")
    assert sm.is_processed("sonarr", "Default", 100) is True


# ── get_stateful_management_info ──────────────────────────────────────────────

def test_get_stateful_management_info_returns_expected_keys(stateful_dir):
    sm.initialize_lock_file()
    info = sm.get_stateful_management_info()
    assert "created_at_ts" in info
    assert "expires_at_ts" in info
    assert "interval_hours" in info


def test_get_stateful_management_info_interval_hours_reflects_setting(stateful_dir):
    sm.initialize_lock_file()
    with patch("src.primary.stateful_manager.get_advanced_setting", return_value=72):
        info = sm.get_stateful_management_info()
    assert info["interval_hours"] == 72

"""Tests for src/primary/state.py — processed ID persistence and state reset."""
import datetime
import json
import os
from unittest.mock import patch

import pytest

from src.primary.state import (
    check_state_reset,
    get_last_reset_time,
    load_processed_ids,
    save_processed_id,
    save_processed_ids,
    set_last_reset_time,
    truncate_processed_list,
)


# ── load_processed_ids ────────────────────────────────────────────────────────

def test_load_processed_ids_no_file_returns_empty(tmp_path):
    result = load_processed_ids(str(tmp_path / "missing.json"))
    assert result == []


def test_load_processed_ids_empty_file_returns_empty(tmp_path):
    f = tmp_path / "ids.json"
    f.write_text("[]")
    assert load_processed_ids(str(f)) == []


def test_load_processed_ids_round_trip(tmp_path):
    f = tmp_path / "ids.json"
    ids = [1, 2, 3, 100, 999]
    save_processed_ids(str(f), ids)
    assert load_processed_ids(str(f)) == ids


def test_load_processed_ids_invalid_json_returns_empty(tmp_path):
    f = tmp_path / "ids.json"
    f.write_text("not valid json {{{")
    assert load_processed_ids(str(f)) == []


def test_load_processed_ids_non_list_json_returns_empty(tmp_path):
    f = tmp_path / "ids.json"
    f.write_text('{"key": "value"}')
    assert load_processed_ids(str(f)) == []


# ── save_processed_ids ────────────────────────────────────────────────────────

def test_save_processed_ids_creates_file(tmp_path):
    f = tmp_path / "ids.json"
    save_processed_ids(str(f), [10, 20])
    assert f.exists()
    assert json.loads(f.read_text()) == [10, 20]


def test_save_processed_ids_overwrites_existing(tmp_path):
    f = tmp_path / "ids.json"
    save_processed_ids(str(f), [1, 2, 3])
    save_processed_ids(str(f), [99])
    assert load_processed_ids(str(f)) == [99]


# ── save_processed_id ─────────────────────────────────────────────────────────

def test_save_processed_id_appends_new(tmp_path):
    f = tmp_path / "ids.json"
    save_processed_ids(str(f), [1, 2])
    save_processed_id(str(f), 3)
    assert 3 in load_processed_ids(str(f))


def test_save_processed_id_no_duplicate(tmp_path):
    f = tmp_path / "ids.json"
    save_processed_ids(str(f), [1, 2, 3])
    save_processed_id(str(f), 2)
    result = load_processed_ids(str(f))
    assert result.count(2) == 1


# ── truncate_processed_list ───────────────────────────────────────────────────

def test_truncate_honours_max_items(tmp_path):
    f = tmp_path / "ids.json"
    save_processed_ids(str(f), list(range(200)))
    truncate_processed_list(str(f), max_items=50)
    result = load_processed_ids(str(f))
    assert len(result) == 50
    # Keeps the LAST N items
    assert result == list(range(150, 200))


def test_truncate_no_op_when_under_limit(tmp_path):
    f = tmp_path / "ids.json"
    ids = [1, 2, 3]
    save_processed_ids(str(f), ids)
    truncate_processed_list(str(f), max_items=100)
    assert load_processed_ids(str(f)) == ids


def test_truncate_exact_limit_is_no_op(tmp_path):
    f = tmp_path / "ids.json"
    ids = list(range(10))
    save_processed_ids(str(f), ids)
    truncate_processed_list(str(f), max_items=10)
    assert load_processed_ids(str(f)) == ids


# ── last reset time ───────────────────────────────────────────────────────────

def test_get_last_reset_time_no_file_returns_epoch(config_dir):
    result = get_last_reset_time("sonarr")
    assert result == datetime.datetime.fromtimestamp(0)


def test_get_last_reset_time_no_app_type_returns_epoch(config_dir):
    result = get_last_reset_time(None)
    assert result == datetime.datetime.fromtimestamp(0)


def test_set_and_get_last_reset_time_round_trips(config_dir):
    now = datetime.datetime(2026, 1, 15, 12, 0, 0)
    set_last_reset_time(now, "sonarr")
    result = get_last_reset_time("sonarr")
    assert result == now


# ── check_state_reset ─────────────────────────────────────────────────────────

def test_check_state_reset_triggers_after_double_interval(config_dir):
    """Reset fires when hours_passed >= interval * 2 (double-interval safeguard)."""
    # Use a 1-hour interval; set last reset 3 hours ago so 3h >= 2 * 1h
    long_ago = datetime.datetime.now() - datetime.timedelta(hours=3)
    set_last_reset_time(long_ago, "sonarr")

    with patch("src.primary.state.settings_manager.get_advanced_setting", return_value=1):
        result = check_state_reset("sonarr")

    assert result is True


def test_check_state_reset_does_not_trigger_before_double_interval(config_dir):
    """Reset does NOT fire when hours_passed is between 1x and 2x interval."""
    # 1-hour interval; last reset 1.5 hours ago (between 1x and 2x)
    recent = datetime.datetime.now() - datetime.timedelta(hours=1, minutes=30)
    set_last_reset_time(recent, "sonarr")

    with patch("src.primary.state.settings_manager.get_advanced_setting", return_value=1):
        result = check_state_reset("sonarr")

    assert result is False


def test_check_state_reset_no_app_type_returns_false(config_dir):
    assert check_state_reset(None) is False

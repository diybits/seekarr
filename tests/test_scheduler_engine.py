"""Tests for src/primary/scheduler_engine.py — load, history, scheduling, execution."""
import collections
import datetime as _dt
import json
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

import src.primary.scheduler_engine as engine


# ── Helpers ───────────────────────────────────────────────────────────────────

# 2026-05-18 is a Monday; 2026-05-19 is a Tuesday.
MONDAY = _dt.datetime(2026, 5, 18, 14, 30, 0)
TUESDAY = _dt.datetime(2026, 5, 19, 14, 30, 0)


@contextmanager
def freeze_now(fake_now):
    """Patch datetime.datetime.now() inside scheduler_engine to return fake_now."""
    with patch("src.primary.scheduler_engine.datetime") as mock_mod:
        mock_mod.datetime.now.return_value = fake_now
        mock_mod.timedelta = _dt.timedelta
        yield mock_mod


def make_entry(hour, minute, *, action="disable", app="sonarr",
               days=None, enabled=True, entry_id="t1"):
    entry = {
        "id": entry_id,
        "action": action,
        "app": app,
        "hour": hour,
        "minute": minute,
        "enabled": enabled,
    }
    if days is not None:
        entry["days"] = days
    return entry


def write_app_config(cfg_dir, app, data):
    path = cfg_dir / f"{app}.json"
    path.write_text(json.dumps(data))
    return path


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset module-level mutable state between every test."""
    monkeypatch.setattr(engine, "last_executed_actions", {})
    monkeypatch.setattr(engine, "execution_history",
                        collections.deque(maxlen=engine.max_history_entries))


@pytest.fixture
def schedule_dir(tmp_path, monkeypatch):
    sched = tmp_path / "scheduler"
    sched.mkdir()
    sched_file = sched / "schedule.json"
    monkeypatch.setattr(engine, "SCHEDULE_DIR", str(sched))
    monkeypatch.setattr(engine, "SCHEDULE_FILE", str(sched_file))
    return sched


@pytest.fixture
def app_config_dir(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr(engine, "_CONFIG_DIR", str(cfg))
    return cfg


# ── load_schedule ─────────────────────────────────────────────────────────────

def test_load_schedule_no_file_creates_default(schedule_dir):
    result = engine.load_schedule()
    assert (schedule_dir / "schedule.json").exists()
    for key in ["global", "sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        assert result[key] == []


def test_load_schedule_empty_file_returns_default(schedule_dir):
    (schedule_dir / "schedule.json").write_text("")
    result = engine.load_schedule()
    assert result["sonarr"] == []


def test_load_schedule_valid_json_returned(schedule_dir):
    data = {"sonarr": [{"id": "s1", "action": "disable"}], "global": []}
    (schedule_dir / "schedule.json").write_text(json.dumps(data))
    result = engine.load_schedule()
    assert result["sonarr"] == [{"id": "s1", "action": "disable"}]


def test_load_schedule_back_fills_missing_app_keys(schedule_dir):
    (schedule_dir / "schedule.json").write_text(json.dumps({"sonarr": []}))
    result = engine.load_schedule()
    for key in ["global", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        assert key in result


def test_load_schedule_corrupted_json_backs_up_and_returns_default(schedule_dir):
    (schedule_dir / "schedule.json").write_text("not valid json {{{")
    result = engine.load_schedule()
    backups = [f for f in os.listdir(schedule_dir) if "backup" in f]
    assert len(backups) == 1
    assert (schedule_dir / "schedule.json").exists()
    assert result["sonarr"] == []


# ── add_to_history ────────────────────────────────────────────────────────────

def test_add_to_history_entry_has_expected_fields():
    engine.add_to_history({"id": "abc", "action": "disable", "app": "sonarr"},
                          "success", "done")
    h = list(engine.execution_history)
    assert h[0]["id"] == "abc"
    assert h[0]["action"] == "disable"
    assert h[0]["app"] == "sonarr"
    assert h[0]["status"] == "success"
    assert h[0]["message"] == "done"
    assert "timestamp" in h[0]


def test_add_to_history_most_recent_entry_is_first():
    engine.add_to_history({"id": "1", "action": "a", "app": "x"}, "ok", "first")
    engine.add_to_history({"id": "2", "action": "b", "app": "y"}, "ok", "second")
    h = list(engine.execution_history)
    assert h[0]["id"] == "2"
    assert h[1]["id"] == "1"


def test_add_to_history_respects_maxlen(monkeypatch):
    monkeypatch.setattr(engine, "execution_history", collections.deque(maxlen=3))
    for i in range(5):
        engine.add_to_history({"id": str(i), "action": "a", "app": "x"}, "ok", "m")
    assert len(engine.execution_history) == 3


# ── should_execute_schedule — enabled / day checks ───────────────────────────

def test_disabled_entry_returns_false():
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(14, 30, enabled=False)) is False


def test_today_not_in_days_returns_false():
    # MONDAY.strftime("%A").lower() == "monday"
    entry = make_entry(14, 30, days=["tuesday", "wednesday"])
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is False


def test_today_in_days_passes_day_check():
    entry = make_entry(14, 30, days=["monday"])
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is True


def test_days_comparison_is_case_insensitive():
    entry = make_entry(14, 30, days=["Monday", "TUESDAY"])
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is True


def test_empty_days_runs_every_day():
    entry = make_entry(14, 30, days=[])
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is True


# ── should_execute_schedule — time window ────────────────────────────────────

def test_current_hour_before_scheduled_returns_false():
    # Scheduled 15:00, now 14:30
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(15, 0)) is False


def test_same_hour_minute_before_scheduled_returns_false():
    # Scheduled 14:45, now 14:30
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(14, 45)) is False


def test_exactly_at_scheduled_time_returns_true():
    # Scheduled 14:30, now 14:30
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(14, 30)) is True


def test_within_4_minute_window_returns_true():
    # Scheduled 14:28, now 14:30 → 2 min late, still in window
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(14, 28)) is True


def test_past_4_minute_window_returns_false():
    # Scheduled 14:25, now 14:30 → 5 min late, window closed
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(make_entry(14, 25)) is False


def test_hour_rollover_within_window_returns_true():
    # Scheduled 13:59, now 14:00 → 1 min late across hour boundary
    rollover = _dt.datetime(2026, 5, 18, 14, 0, 0)
    with freeze_now(rollover):
        assert engine.should_execute_schedule(make_entry(13, 59)) is True


def test_hour_rollover_does_not_apply_when_minute_below_57():
    # Scheduled 13:55 — minute < 57, so rollover window doesn't apply
    rollover = _dt.datetime(2026, 5, 18, 14, 0, 0)
    with freeze_now(rollover):
        assert engine.should_execute_schedule(make_entry(13, 55)) is False


def test_invalid_time_format_returns_false():
    # Entry has no hour/minute keys
    entry = {"id": "t1", "action": "disable", "app": "sonarr", "enabled": True}
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is False


def test_nested_time_format_is_supported():
    # Some entries use time.hour / time.minute instead of flat keys
    entry = {
        "id": "t1", "action": "disable", "app": "sonarr", "enabled": True,
        "time": {"hour": 14, "minute": 30},
    }
    with freeze_now(MONDAY):
        assert engine.should_execute_schedule(entry) is True


# ── execute_action — already-executed guard ───────────────────────────────────

def test_execute_action_skips_if_already_executed_today():
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    engine.last_executed_actions[f"job-1_{today}"] = _dt.datetime.now()
    result = engine.execute_action(make_entry(14, 30, entry_id="job-1"))
    assert result is False


# ── execute_action — disable / pause ─────────────────────────────────────────

def test_execute_action_disable_sets_enabled_false(app_config_dir):
    write_app_config(app_config_dir, "sonarr", {"enabled": True})
    result = engine.execute_action(make_entry(14, 30, action="disable", app="sonarr"))
    assert result is True
    assert json.loads((app_config_dir / "sonarr.json").read_text())["enabled"] is False


def test_execute_action_pause_is_alias_for_disable(app_config_dir):
    write_app_config(app_config_dir, "sonarr", {"enabled": True})
    engine.execute_action(make_entry(14, 30, action="pause", app="sonarr"))
    assert json.loads((app_config_dir / "sonarr.json").read_text())["enabled"] is False


def test_execute_action_disable_updates_instances_array(app_config_dir):
    cfg = {"enabled": True, "instances": [{"enabled": True, "url": "http://x"}]}
    write_app_config(app_config_dir, "sonarr", cfg)
    engine.execute_action(make_entry(14, 30, action="disable", app="sonarr"))
    data = json.loads((app_config_dir / "sonarr.json").read_text())
    assert data["instances"][0]["enabled"] is False


def test_execute_action_disable_global_disables_all_apps(app_config_dir):
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        write_app_config(app_config_dir, app, {"enabled": True})
    engine.execute_action(make_entry(14, 30, action="disable", app="global"))
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        data = json.loads((app_config_dir / f"{app}.json").read_text())
        assert data["enabled"] is False, f"{app} should be disabled"


def test_execute_action_disable_missing_config_is_no_op(app_config_dir):
    # File doesn't exist — should not crash, still returns True
    result = engine.execute_action(make_entry(14, 30, action="disable", app="sonarr"))
    assert result is True


# ── execute_action — enable / resume ─────────────────────────────────────────

def test_execute_action_enable_sets_enabled_true(app_config_dir):
    write_app_config(app_config_dir, "radarr", {"enabled": False})
    engine.execute_action(make_entry(14, 30, action="enable", app="radarr"))
    assert json.loads((app_config_dir / "radarr.json").read_text())["enabled"] is True


def test_execute_action_resume_is_alias_for_enable(app_config_dir):
    write_app_config(app_config_dir, "radarr", {"enabled": False})
    engine.execute_action(make_entry(14, 30, action="resume", app="radarr"))
    assert json.loads((app_config_dir / "radarr.json").read_text())["enabled"] is True


def test_execute_action_enable_global_enables_all_apps(app_config_dir):
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        write_app_config(app_config_dir, app, {"enabled": False})
    engine.execute_action(make_entry(14, 30, action="enable", app="global"))
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        data = json.loads((app_config_dir / f"{app}.json").read_text())
        assert data["enabled"] is True, f"{app} should be enabled"


# ── execute_action — api cap ──────────────────────────────────────────────────

def test_execute_action_api_limit_dash_format(app_config_dir):
    write_app_config(app_config_dir, "sonarr", {"hourly_cap": 20})
    engine.execute_action(make_entry(14, 30, action="api-5", app="sonarr"))
    assert json.loads((app_config_dir / "sonarr.json").read_text())["hourly_cap"] == 5


def test_execute_action_api_limit_space_format(app_config_dir):
    write_app_config(app_config_dir, "sonarr", {"hourly_cap": 20})
    engine.execute_action(make_entry(14, 30, action="API Limits 10", app="sonarr"))
    assert json.loads((app_config_dir / "sonarr.json").read_text())["hourly_cap"] == 10


def test_execute_action_api_limit_global_sets_all_apps(app_config_dir):
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        write_app_config(app_config_dir, app, {"hourly_cap": 20})
    engine.execute_action(make_entry(14, 30, action="api-3", app="global"))
    for app in ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
        data = json.loads((app_config_dir / f"{app}.json").read_text())
        assert data["hourly_cap"] == 3, f"{app} cap should be 3"


def test_execute_action_invalid_api_format_returns_false(app_config_dir):
    result = engine.execute_action(make_entry(14, 30, action="api-xyz", app="sonarr"))
    assert result is False


# ── execute_action — post-execution state ────────────────────────────────────

def test_execute_action_marks_execution_key_after_success(app_config_dir):
    write_app_config(app_config_dir, "sonarr", {"enabled": True})
    engine.execute_action(make_entry(14, 30, action="disable", app="sonarr",
                                     entry_id="job-99"))
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    assert f"job-99_{today}" in engine.last_executed_actions


# ── get_execution_history ─────────────────────────────────────────────────────

def test_get_execution_history_returns_list():
    engine.add_to_history({"id": "1", "action": "a", "app": "x"}, "ok", "m")
    assert isinstance(engine.get_execution_history(), list)


def test_get_execution_history_newest_first():
    engine.add_to_history({"id": "1", "action": "a", "app": "x"}, "ok", "first")
    engine.add_to_history({"id": "2", "action": "b", "app": "y"}, "ok", "second")
    h = engine.get_execution_history()
    assert h[0]["id"] == "2"
    assert h[1]["id"] == "1"

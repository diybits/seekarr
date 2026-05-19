"""Tests for src/primary/background.py

Covers the well-isolated functions (reset_app_cycle, shutdown_handler,
start_app_threads, check_and_restart_threads, scheduler helpers) and the
key early-exit paths in app_specific_loop.
"""
import threading
import datetime
from unittest.mock import MagicMock, patch, mock_open

import pytest

import src.primary.background as background


# ── Fixture: reset module-level globals between tests ────────────────────────

@pytest.fixture(autouse=True)
def reset_state():
    """Isolate module-level threading state from test to test."""
    background.stop_event = threading.Event()
    background.app_threads = {}
    background.hourly_cap_scheduler_thread = None
    background.instance_list_generator_thread = None
    yield


# ── reset_app_cycle ───────────────────────────────────────────────────────────

def test_reset_app_cycle_returns_true_on_success(monkeypatch, tmp_path):
    reset_dir = tmp_path / "reset"
    reset_dir.mkdir()
    monkeypatch.setattr("src.primary.background.open",
                        mock_open(), raising=False)
    with patch("builtins.open", mock_open()):
        result = background.reset_app_cycle("sonarr")
    assert result is True


def test_reset_app_cycle_returns_false_on_io_error():
    with patch("builtins.open", side_effect=OSError("permission denied")):
        result = background.reset_app_cycle("sonarr")
    assert result is False


# ── shutdown_handler ──────────────────────────────────────────────────────────

def test_shutdown_handler_sets_stop_event():
    assert not background.stop_event.is_set()
    background.shutdown_handler(15, None)
    assert background.stop_event.is_set()


# ── start_app_threads ─────────────────────────────────────────────────────────

def _make_fake_thread_factory(started):
    """Return a Thread replacement that records which app_type was passed."""
    def fake_thread(**kwargs):
        t = MagicMock()
        t.is_alive.return_value = False
        args = kwargs.get("args", ())
        t.start.side_effect = lambda: started.append(args[0] if args else kwargs.get("name"))
        return t
    return fake_thread


def test_start_app_threads_starts_thread_for_configured_app(monkeypatch):
    monkeypatch.setattr("src.primary.background.settings_manager.get_configured_apps",
                        lambda: ["sonarr"])
    started = []
    monkeypatch.setattr("src.primary.background.threading.Thread",
                        _make_fake_thread_factory(started))
    background.start_app_threads()
    assert "sonarr" in started


def test_start_app_threads_skips_already_alive_thread(monkeypatch):
    monkeypatch.setattr("src.primary.background.settings_manager.get_configured_apps",
                        lambda: ["radarr"])
    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    background.app_threads["radarr"] = alive_thread

    started = []
    monkeypatch.setattr("src.primary.background.threading.Thread",
                        _make_fake_thread_factory(started))
    background.start_app_threads()
    assert "radarr" not in started


def test_start_app_threads_starts_multiple_apps(monkeypatch):
    monkeypatch.setattr("src.primary.background.settings_manager.get_configured_apps",
                        lambda: ["sonarr", "radarr"])
    started = []
    monkeypatch.setattr("src.primary.background.threading.Thread",
                        _make_fake_thread_factory(started))
    background.start_app_threads()
    assert set(started) == {"sonarr", "radarr"}


# ── check_and_restart_threads ─────────────────────────────────────────────────

def test_check_and_restart_threads_restarts_dead_thread(monkeypatch):
    monkeypatch.setattr("src.primary.background.settings_manager.get_configured_apps",
                        lambda: ["sonarr"])
    dead = MagicMock()
    dead.is_alive.return_value = False
    background.app_threads["sonarr"] = dead

    started = []
    monkeypatch.setattr("src.primary.background.threading.Thread",
                        _make_fake_thread_factory(started))
    background.check_and_restart_threads()
    assert "sonarr" in started


def test_check_and_restart_threads_does_not_restart_unconfigured(monkeypatch):
    monkeypatch.setattr("src.primary.background.settings_manager.get_configured_apps",
                        lambda: [])
    dead = MagicMock()
    dead.is_alive.return_value = False
    background.app_threads["sonarr"] = dead

    started = []
    monkeypatch.setattr("src.primary.background.threading.Thread",
                        _make_fake_thread_factory(started))
    background.check_and_restart_threads()
    assert started == []


# ── start_hourly_cap_scheduler ────────────────────────────────────────────────

def test_start_hourly_cap_scheduler_creates_thread(monkeypatch):
    started = []
    def fake_thread(**kwargs):
        t = MagicMock()
        t.is_alive.return_value = True
        t.start.side_effect = lambda: started.append(kwargs.get("name"))
        return t
    monkeypatch.setattr("src.primary.background.threading.Thread", fake_thread)
    background.start_hourly_cap_scheduler()
    assert "HourlyCapScheduler" in started


def test_start_hourly_cap_scheduler_no_duplicate_if_alive(monkeypatch):
    alive = MagicMock()
    alive.is_alive.return_value = True
    background.hourly_cap_scheduler_thread = alive

    started = []
    def fake_thread(**kw):
        t = MagicMock()
        t.start.side_effect = lambda: started.append("new")
        return t
    monkeypatch.setattr("src.primary.background.threading.Thread", fake_thread)
    background.start_hourly_cap_scheduler()
    assert started == []


# ── start_instance_list_generator ────────────────────────────────────────────

def test_start_instance_list_generator_creates_thread(monkeypatch):
    started = []
    def fake_thread(**kwargs):
        t = MagicMock()
        t.is_alive.return_value = True
        t.start.side_effect = lambda: started.append(kwargs.get("name"))
        return t
    monkeypatch.setattr("src.primary.background.threading.Thread", fake_thread)
    background.start_instance_list_generator()
    assert "InstanceListGenerator" in started


def test_start_instance_list_generator_no_duplicate_if_alive(monkeypatch):
    alive = MagicMock()
    alive.is_alive.return_value = True
    background.instance_list_generator_thread = alive

    started = []
    def fake_thread(**kw):
        t = MagicMock()
        t.start.side_effect = lambda: started.append("new")
        return t
    monkeypatch.setattr("src.primary.background.threading.Thread", fake_thread)
    background.start_instance_list_generator()
    assert started == []


# ── instance_list_generator_loop ──────────────────────────────────────────────

def test_instance_list_generator_loop_calls_generate_and_exits(monkeypatch):
    calls = []
    monkeypatch.setattr("src.primary.background.generate_instance_list",
                        lambda: calls.append(1) or {})
    # Set stop_event during wait() so the loop runs once then exits
    def stop_on_wait(timeout):
        background.stop_event.set()
    background.stop_event.wait = stop_on_wait
    background.instance_list_generator_loop()
    assert len(calls) == 1


# ── hourly_cap_scheduler_loop ─────────────────────────────────────────────────

def test_hourly_cap_scheduler_loop_exits_on_stop_event(monkeypatch):
    reset_calls = []
    monkeypatch.setattr("src.primary.background.stop_event",
                        background.stop_event)
    # Provide the reset_hourly_caps via the import inside the function
    with patch("src.primary.stats_manager.reset_hourly_caps",
               side_effect=lambda: reset_calls.append(1) or True):
        background.stop_event.set()  # exit immediately
        background.hourly_cap_scheduler_loop()
    # Should exit without error; reset_calls may or may not fire at minute 0


def test_hourly_cap_scheduler_loop_resets_caps_at_top_of_hour(monkeypatch):
    reset_calls = []
    # Patch datetime to return minute=0 so the reset fires
    fake_now = MagicMock()
    fake_now.minute = 0
    fake_now.hour = 12

    with patch("src.primary.background.datetime") as mock_dt, \
         patch("src.primary.stats_manager.reset_hourly_caps",
               return_value=True) as mock_reset:
        mock_dt.datetime.now.return_value = fake_now

        # Let the loop run one outer check then stop
        call_count = [0]
        real_wait = background.stop_event.wait
        def controlled_wait(timeout):
            call_count[0] += 1
            if call_count[0] >= 2:
                background.stop_event.set()
        background.stop_event.wait = controlled_wait

        background.hourly_cap_scheduler_loop()
        assert mock_reset.called


# ── app_specific_loop — early-exit paths ─────────────────────────────────────

def test_app_specific_loop_exits_immediately_for_invalid_app_type():
    # Unknown type hits the else branch and returns without ever entering the while loop
    background.stop_event.set()  # also ensure loop can't run
    # Should return without raising
    background.app_specific_loop("invalid_app_type_xyz")


def test_app_specific_loop_exits_when_stop_event_already_set(monkeypatch):
    # Valid app type but stop_event is already set → while loop body never runs
    monkeypatch.setattr("src.primary.background.settings_manager.load_settings",
                        lambda *a: None)
    background.stop_event.set()
    # Should complete without calling load_settings in the loop body
    background.app_specific_loop("radarr")


def test_app_specific_loop_retries_after_settings_load_failure(monkeypatch):
    load_calls = [0]
    def load_settings(app_type):
        load_calls[0] += 1
        if load_calls[0] >= 2:
            background.stop_event.set()  # stop after second call
        return None  # Simulate failure

    monkeypatch.setattr("src.primary.background.settings_manager.load_settings", load_settings)
    monkeypatch.setattr("src.primary.background.stop_event.wait", lambda t: None)
    background.app_specific_loop("radarr")
    assert load_calls[0] >= 2

"""Tests for src/primary/hourly_cap_scheduler.py — cap-reset logic and thread lifecycle."""
import datetime as _dt
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

import src.primary.hourly_cap_scheduler as hcs


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def freeze_now(fake_now):
    """Patch datetime.datetime.now() inside hourly_cap_scheduler."""
    with patch("src.primary.hourly_cap_scheduler.datetime") as mock_mod:
        mock_mod.datetime.now.return_value = fake_now
        yield mock_mod


TOP_OF_HOUR = _dt.datetime(2026, 5, 18, 14, 0, 0)   # minute == 0
MID_HOUR    = _dt.datetime(2026, 5, 18, 14, 30, 0)  # minute == 30


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_thread_state(monkeypatch):
    """Ensure module-level thread state is clean before every test."""
    hcs.stop_event.clear()
    monkeypatch.setattr(hcs, "scheduler_thread", None)
    yield
    # Stop any thread started during the test
    hcs.stop_event.set()
    if hcs.scheduler_thread and hcs.scheduler_thread.is_alive():
        hcs.scheduler_thread.join(timeout=2.0)


# ── check_and_reset_caps — time check ────────────────────────────────────────

def test_reset_called_at_top_of_hour():
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True) as mock_reset:
        with freeze_now(TOP_OF_HOUR):
            hcs.check_and_reset_caps()
    mock_reset.assert_called_once()


def test_reset_not_called_mid_hour():
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True) as mock_reset:
        with freeze_now(MID_HOUR):
            hcs.check_and_reset_caps()
    mock_reset.assert_not_called()


def test_reset_not_called_at_minute_1():
    one_past = _dt.datetime(2026, 5, 18, 14, 1, 0)
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True) as mock_reset:
        with freeze_now(one_past):
            hcs.check_and_reset_caps()
    mock_reset.assert_not_called()


def test_reset_not_called_at_minute_59():
    almost = _dt.datetime(2026, 5, 18, 14, 59, 0)
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True) as mock_reset:
        with freeze_now(almost):
            hcs.check_and_reset_caps()
    mock_reset.assert_not_called()


def test_reset_called_at_midnight():
    midnight = _dt.datetime(2026, 5, 18, 0, 0, 0)
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True) as mock_reset:
        with freeze_now(midnight):
            hcs.check_and_reset_caps()
    mock_reset.assert_called_once()


# ── check_and_reset_caps — reset outcome ─────────────────────────────────────

def test_successful_reset_does_not_raise():
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=True):
        with freeze_now(TOP_OF_HOUR):
            hcs.check_and_reset_caps()  # must not raise


def test_failed_reset_does_not_raise():
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", return_value=False):
        with freeze_now(TOP_OF_HOUR):
            hcs.check_and_reset_caps()  # must not raise


def test_reset_exception_is_swallowed():
    with patch("src.primary.hourly_cap_scheduler.reset_hourly_caps", side_effect=RuntimeError("db down")):
        with freeze_now(TOP_OF_HOUR):
            hcs.check_and_reset_caps()  # must not propagate the exception


def test_datetime_exception_is_swallowed():
    with patch("src.primary.hourly_cap_scheduler.datetime") as mock_mod:
        mock_mod.datetime.now.side_effect = OSError("clock error")
        hcs.check_and_reset_caps()  # must not raise


# ── start_scheduler ───────────────────────────────────────────────────────────

def test_start_scheduler_returns_true():
    result = hcs.start_scheduler()
    assert result is True


def test_start_scheduler_thread_is_alive():
    hcs.start_scheduler()
    assert hcs.scheduler_thread is not None
    assert hcs.scheduler_thread.is_alive()


def test_start_scheduler_thread_is_daemon():
    hcs.start_scheduler()
    assert hcs.scheduler_thread.daemon is True


def test_start_scheduler_when_already_running_returns_none():
    hcs.start_scheduler()
    result = hcs.start_scheduler()
    assert result is None


def test_start_scheduler_clears_stop_event():
    hcs.stop_event.set()
    hcs.start_scheduler()
    assert not hcs.stop_event.is_set()


# ── stop_scheduler ────────────────────────────────────────────────────────────

def test_stop_scheduler_when_not_running_is_no_op():
    hcs.stop_scheduler()  # must not raise


def test_stop_scheduler_terminates_thread():
    hcs.start_scheduler()
    assert hcs.scheduler_thread.is_alive()
    hcs.stop_scheduler()
    hcs.scheduler_thread.join(timeout=3.0)
    assert not hcs.scheduler_thread.is_alive()


def test_stop_scheduler_sets_stop_event():
    hcs.start_scheduler()
    hcs.stop_scheduler()
    assert hcs.stop_event.is_set()


# ── start / stop round-trip ───────────────────────────────────────────────────

def test_restart_after_stop_works():
    hcs.start_scheduler()
    hcs.stop_scheduler()
    hcs.scheduler_thread.join(timeout=3.0)

    hcs.stop_event.clear()
    result = hcs.start_scheduler()
    assert result is True
    assert hcs.scheduler_thread.is_alive()

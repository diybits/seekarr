"""Tests for src/primary/apps/sonarr/missing.py"""
from unittest.mock import MagicMock

import pytest

import src.primary.apps.sonarr.missing as sonarr_missing


_NO_STOP = lambda: False

_EPISODE = {
    "id": 1,
    "title": "Pilot",
    "seriesId": 10,
    "seasonNumber": 1,
    "episodeNumber": 1,
    "airDateUtc": "2020-01-01T00:00:00Z",
    "series": {"title": "Great Show"},
}


def _patch(monkeypatch, *, episodes=None, search_id=99, wait_ok=True, is_proc=False):
    monkeypatch.setattr("src.primary.apps.sonarr.missing.get_advanced_setting", lambda k, d=None: d)
    monkeypatch.setattr("src.primary.apps.sonarr.missing.is_processed", lambda *a: is_proc)
    monkeypatch.setattr("src.primary.apps.sonarr.missing.add_processed_id", MagicMock(return_value=True))
    monkeypatch.setattr("src.primary.apps.sonarr.missing.increment_stat", MagicMock())
    monkeypatch.setattr("src.primary.apps.sonarr.missing.log_processed_media", MagicMock())
    monkeypatch.setattr("src.primary.apps.sonarr.missing.wait_for_command", lambda *a, **k: wait_ok)
    monkeypatch.setattr("src.primary.apps.sonarr.api.get_missing_episodes_random_page",
                        lambda *a, **k: episodes or [])
    monkeypatch.setattr("src.primary.apps.sonarr.api.search_episode", lambda *a, **k: search_id)


def _call(monkeypatch, *, hunt=5, mode="episodes", stop=None, **kw):
    _patch(monkeypatch, **kw)
    return sonarr_missing.process_missing_episodes(
        api_url="http://sonarr:8989",
        api_key="key",
        instance_name="Sonarr",
        api_timeout=30,
        monitored_only=True,
        skip_future_episodes=False,
        hunt_missing_items=hunt,
        hunt_missing_mode=mode,
        command_wait_delay=0,
        command_wait_attempts=0,
        stop_check=stop or _NO_STOP,
    )


def test_returns_false_when_hunt_missing_zero(monkeypatch):
    _patch(monkeypatch)
    assert _call(monkeypatch, hunt=0) is False


def test_invalid_mode_returns_false(monkeypatch):
    _patch(monkeypatch)
    assert _call(monkeypatch, mode="invalid_mode") is False


def test_episodes_mode_no_results_returns_false(monkeypatch):
    assert _call(monkeypatch, episodes=[]) is False


def test_episodes_mode_all_processed_returns_false(monkeypatch):
    assert _call(monkeypatch, episodes=[_EPISODE], is_proc=True) is False


def test_episodes_mode_processes_and_returns_true(monkeypatch):
    result = _call(monkeypatch, episodes=[_EPISODE], wait_ok=True)
    assert result is True


def test_episodes_mode_increments_stat_on_success(monkeypatch):
    _patch(monkeypatch, episodes=[_EPISODE], wait_ok=True)
    inc = MagicMock()
    monkeypatch.setattr("src.primary.apps.sonarr.missing.increment_stat", inc)
    sonarr_missing.process_missing_episodes(
        api_url="http://sonarr:8989", api_key="key", instance_name="Sonarr",
        api_timeout=30, monitored_only=True, skip_future_episodes=False,
        hunt_missing_items=5, hunt_missing_mode="episodes",
        command_wait_delay=0, command_wait_attempts=0, stop_check=_NO_STOP,
    )
    inc.assert_called()
    assert inc.call_args_list[0].args == ("sonarr", "hunted")


def test_episodes_mode_wait_failure_returns_false(monkeypatch):
    result = _call(monkeypatch, episodes=[_EPISODE], search_id=99, wait_ok=False)
    assert result is False


def test_episodes_mode_search_failure_returns_false(monkeypatch):
    result = _call(monkeypatch, episodes=[_EPISODE], search_id=None)
    assert result is False


def test_future_episodes_filtered_when_skip_enabled(monkeypatch):
    future_ep = {**_EPISODE, "airDateUtc": "2099-01-01T00:00:00Z"}
    _patch(monkeypatch, episodes=[future_ep])
    result = sonarr_missing.process_missing_episodes(
        api_url="http://sonarr:8989",
        api_key="key",
        instance_name="Sonarr",
        api_timeout=30,
        monitored_only=True,
        skip_future_episodes=True,
        hunt_missing_items=5,
        hunt_missing_mode="episodes",
        command_wait_delay=0,
        command_wait_attempts=0,
        stop_check=_NO_STOP,
    )
    assert result is False


def test_past_episode_passes_future_filter(monkeypatch):
    _patch(monkeypatch, episodes=[_EPISODE])  # _EPISODE has airDateUtc 2020 — past
    result = sonarr_missing.process_missing_episodes(
        api_url="http://sonarr:8989",
        api_key="key",
        instance_name="Sonarr",
        api_timeout=30,
        monitored_only=True,
        skip_future_episodes=True,
        hunt_missing_items=5,
        hunt_missing_mode="episodes",
        command_wait_delay=0,
        command_wait_attempts=0,
        stop_check=_NO_STOP,
    )
    assert result is True


def test_stop_mid_processing_aborts(monkeypatch):
    calls = iter([False, True])
    result = _call(monkeypatch, episodes=[_EPISODE], stop=lambda: next(calls, True))
    assert result is False


def test_seasons_packs_mode_dispatches(monkeypatch):
    _patch(monkeypatch)
    mock_sp = MagicMock(return_value=False)
    monkeypatch.setattr("src.primary.apps.sonarr.missing.process_missing_seasons_packs_mode", mock_sp)
    _call(monkeypatch, mode="seasons_packs")
    mock_sp.assert_called_once()


def test_shows_mode_dispatches(monkeypatch):
    _patch(monkeypatch)
    mock_shows = MagicMock(return_value=False)
    monkeypatch.setattr("src.primary.apps.sonarr.missing.process_missing_shows_mode", mock_shows)
    _call(monkeypatch, mode="shows")
    mock_shows.assert_called_once()

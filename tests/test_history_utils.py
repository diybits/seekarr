"""Tests for src/primary/utils/history_utils.py — log_processed_media."""
from unittest.mock import patch

import pytest

import src.primary.utils.history_utils as hu


def test_success_returns_true():
    with patch("src.primary.utils.history_utils.add_history_entry",
               return_value={"processed_info": "Show S01E01"}):
        assert hu.log_processed_media("sonarr", "Show S01E01", 42, "Default") is True


def test_failure_returns_false():
    with patch("src.primary.utils.history_utils.add_history_entry", return_value=None):
        assert hu.log_processed_media("sonarr", "Show S01E01", 42, "Default") is False


def test_exception_returns_false():
    with patch("src.primary.utils.history_utils.add_history_entry",
               side_effect=RuntimeError("disk error")):
        assert hu.log_processed_media("sonarr", "Show", 1, "Default") is False


def test_passes_correct_entry_data():
    captured = {}
    def fake_add(app_type, entry):
        captured["app_type"] = app_type
        captured["entry"] = entry
        return {"processed_info": "Movie"}

    with patch("src.primary.utils.history_utils.add_history_entry", side_effect=fake_add):
        hu.log_processed_media("radarr", "Movie", 7, "MyInstance", operation_type="upgrade")

    assert captured["app_type"] == "radarr"
    assert captured["entry"]["name"] == "Movie"
    assert captured["entry"]["id"] == "7"
    assert captured["entry"]["instance_name"] == "MyInstance"
    assert captured["entry"]["operation_type"] == "upgrade"


def test_media_id_converted_to_string():
    captured = {}
    def fake_add(app_type, entry):
        captured["id"] = entry["id"]
        return {"processed_info": "x"}

    with patch("src.primary.utils.history_utils.add_history_entry", side_effect=fake_add):
        hu.log_processed_media("sonarr", "Show", 123, "Default")

    assert captured["id"] == "123"


def test_default_operation_type_is_missing():
    captured = {}
    def fake_add(app_type, entry):
        captured["op"] = entry["operation_type"]
        return {"processed_info": "x"}

    with patch("src.primary.utils.history_utils.add_history_entry", side_effect=fake_add):
        hu.log_processed_media("sonarr", "Show", 1, "Default")

    assert captured["op"] == "missing"

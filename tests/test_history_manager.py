"""Tests for src/primary/history_manager.py — entries, search, pagination, clear, rename."""
import json
import pathlib

import pytest

import src.primary.history_manager as hm


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def history_dir(tmp_path, monkeypatch):
    hist = tmp_path / "history"
    hist.mkdir()
    monkeypatch.setattr(hm, "HISTORY_BASE_PATH", hist)
    return hist


def _entry(name="Show S01E01", instance="Default", item_id=1, op="missing"):
    return {"name": name, "instance_name": instance, "id": item_id,
            "operation_type": op}


def _add_entries(app, count, instance="Default", id_offset=0):
    for i in range(count):
        hm.add_history_entry(app, _entry(name=f"Item {i}", item_id=id_offset + i,
                                          instance=instance))


# ── get_history_file_path ─────────────────────────────────────────────────────

def test_get_history_file_path_none_instance_uses_default(history_dir):
    p = hm.get_history_file_path("sonarr", None)
    assert p.name == "Default.json"
    assert p.parent.name == "sonarr"


def test_get_history_file_path_spaces_become_underscores(history_dir):
    p = hm.get_history_file_path("sonarr", "My Server")
    assert p.name == "My_Server.json"


def test_get_history_file_path_special_chars_become_underscores(history_dir):
    p = hm.get_history_file_path("radarr", "Server-01")
    assert p.name == "Server_01.json"


# ── format_time_ago ───────────────────────────────────────────────────────────

def test_format_time_ago_seconds_singular():
    assert hm.format_time_ago(1) == "1 second ago"


def test_format_time_ago_seconds_plural():
    assert hm.format_time_ago(45) == "45 seconds ago"


def test_format_time_ago_minutes_singular():
    assert hm.format_time_ago(60) == "1 minute ago"


def test_format_time_ago_minutes_plural():
    assert hm.format_time_ago(125) == "2 minutes ago"


def test_format_time_ago_hours_singular():
    assert hm.format_time_ago(3600) == "1 hour ago"


def test_format_time_ago_hours_plural():
    assert hm.format_time_ago(7200) == "2 hours ago"


def test_format_time_ago_days_singular():
    assert hm.format_time_ago(86400) == "1 day ago"


def test_format_time_ago_days_plural():
    assert hm.format_time_ago(172800) == "2 days ago"


# ── ensure_history_dir ────────────────────────────────────────────────────────

def test_ensure_history_dir_creates_all_app_subdirs(history_dir):
    assert hm.ensure_history_dir() is True
    for app in hm.history_locks.keys():
        assert (history_dir / app).is_dir(), f"subdir missing for {app}"


def test_ensure_history_dir_is_idempotent(history_dir):
    hm.ensure_history_dir()
    assert hm.ensure_history_dir() is True


# ── add_history_entry ─────────────────────────────────────────────────────────

def test_add_history_entry_returns_entry_with_expected_fields(history_dir):
    result = hm.add_history_entry("sonarr", _entry())
    assert result is not None
    assert result["processed_info"] == "Show S01E01"
    assert result["app_type"] == "sonarr"
    assert result["instance_name"] == "Default"
    assert result["operation_type"] == "missing"
    assert "date_time" in result
    assert "date_time_readable" in result


def test_add_history_entry_persists_to_disk(history_dir):
    hm.add_history_entry("sonarr", _entry(name="Movie A"))
    data = json.loads(hm.get_history_file_path("sonarr", "Default").read_text())
    assert len(data) == 1
    assert data[0]["processed_info"] == "Movie A"


def test_add_history_entry_newest_is_first_in_file(history_dir):
    hm.add_history_entry("sonarr", _entry(name="First", item_id=1))
    hm.add_history_entry("sonarr", _entry(name="Second", item_id=2))
    data = json.loads(hm.get_history_file_path("sonarr", "Default").read_text())
    assert data[0]["processed_info"] == "Second"
    assert data[1]["processed_info"] == "First"


def test_add_history_entry_defaults_operation_type_to_missing(history_dir):
    result = hm.add_history_entry("sonarr", {"name": "Show", "instance_name": "Default", "id": 1})
    assert result["operation_type"] == "missing"


def test_add_history_entry_invalid_app_returns_none(history_dir):
    assert hm.add_history_entry("unknownapp", _entry()) is None


def test_add_history_entry_missing_required_field_returns_none(history_dir):
    # Missing instance_name
    assert hm.add_history_entry("sonarr", {"name": "Show", "id": 1}) is None


def test_add_history_entry_recovers_from_corrupt_file(history_dir):
    corrupt = hm.get_history_file_path("sonarr", "Default")
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("not valid json {{{")
    result = hm.add_history_entry("sonarr", _entry())
    assert result is not None
    data = json.loads(corrupt.read_text())
    assert len(data) == 1


# ── get_history ───────────────────────────────────────────────────────────────

def test_get_history_returns_correct_count(history_dir):
    _add_entries("sonarr", 3)
    result = hm.get_history("sonarr")
    assert result["total_entries"] == 3
    assert len(result["entries"]) == 3


def test_get_history_invalid_app_returns_empty(history_dir):
    result = hm.get_history("unknownapp")
    assert result["entries"] == []
    assert result["total_entries"] == 0


def test_get_history_all_combines_apps(history_dir):
    _add_entries("sonarr", 2)
    _add_entries("radarr", 3)
    assert hm.get_history("all")["total_entries"] == 5


def test_get_history_entries_include_how_long_ago(history_dir):
    _add_entries("sonarr", 1)
    result = hm.get_history("sonarr")
    assert "how_long_ago" in result["entries"][0]


def test_get_history_search_filters_by_name(history_dir):
    hm.add_history_entry("sonarr", _entry(name="Breaking Bad S01E01", item_id=1))
    hm.add_history_entry("sonarr", _entry(name="The Wire S02E03", item_id=2))
    result = hm.get_history("sonarr", search_query="breaking")
    assert result["total_entries"] == 1
    assert result["entries"][0]["processed_info"] == "Breaking Bad S01E01"


def test_get_history_search_is_case_insensitive(history_dir):
    hm.add_history_entry("sonarr", _entry(name="Breaking Bad S01E01"))
    assert hm.get_history("sonarr", search_query="BREAKING")["total_entries"] == 1


def test_get_history_pagination(history_dir):
    _add_entries("sonarr", 25)
    result = hm.get_history("sonarr", page=2, page_size=10)
    assert result["total_entries"] == 25
    assert result["total_pages"] == 3
    assert result["current_page"] == 2
    assert len(result["entries"]) == 10


def test_get_history_page_out_of_bounds_clamps_to_valid(history_dir):
    _add_entries("sonarr", 5)
    result = hm.get_history("sonarr", page=99, page_size=10)
    assert result["current_page"] == 1


def test_get_history_empty_returns_one_total_page(history_dir):
    result = hm.get_history("sonarr")
    assert result["total_pages"] == 1
    assert result["total_entries"] == 0


# ── clear_history ─────────────────────────────────────────────────────────────

def test_clear_history_specific_app(history_dir):
    _add_entries("sonarr", 3)
    assert hm.clear_history("sonarr") is True
    assert hm.get_history("sonarr")["total_entries"] == 0


def test_clear_history_leaves_other_apps_intact(history_dir):
    _add_entries("sonarr", 2)
    _add_entries("radarr", 3)
    hm.clear_history("sonarr")
    assert hm.get_history("radarr")["total_entries"] == 3


def test_clear_history_all_wipes_every_app(history_dir):
    _add_entries("sonarr", 2)
    _add_entries("radarr", 2)
    hm.clear_history("all")
    assert hm.get_history("all")["total_entries"] == 0


def test_clear_history_invalid_app_returns_false(history_dir):
    assert hm.clear_history("unknownapp") is False


# ── handle_instance_rename ────────────────────────────────────────────────────

def test_handle_instance_rename_moves_entries_to_new_file(history_dir):
    _add_entries("sonarr", 3, instance="OldName")
    assert hm.handle_instance_rename("sonarr", "OldName", "NewName") is True
    assert not hm.get_history_file_path("sonarr", "OldName").exists()
    data = json.loads(hm.get_history_file_path("sonarr", "NewName").read_text())
    assert len(data) == 3


def test_handle_instance_rename_updates_instance_name_in_entries(history_dir):
    _add_entries("sonarr", 2, instance="OldName")
    hm.handle_instance_rename("sonarr", "OldName", "NewName")
    data = json.loads(hm.get_history_file_path("sonarr", "NewName").read_text())
    assert all(e["instance_name"] == "NewName" for e in data)


def test_handle_instance_rename_merges_with_existing_target(history_dir):
    # Use distinct id ranges to guarantee no deduplication
    _add_entries("sonarr", 2, instance="OldName", id_offset=0)
    _add_entries("sonarr", 3, instance="NewName", id_offset=100)
    hm.handle_instance_rename("sonarr", "OldName", "NewName")
    data = json.loads(hm.get_history_file_path("sonarr", "NewName").read_text())
    assert len(data) == 5


def test_handle_instance_rename_same_name_is_no_op(history_dir):
    assert hm.handle_instance_rename("sonarr", "Same", "Same") is True


def test_handle_instance_rename_invalid_app_returns_false(history_dir):
    assert hm.handle_instance_rename("unknownapp", "A", "B") is False


# ── initialize_instance_history ───────────────────────────────────────────────

def test_initialize_instance_history_creates_empty_file(history_dir):
    path = hm.initialize_instance_history("sonarr", "MyInstance")
    assert path is not None
    assert pathlib.Path(path).exists()
    assert json.loads(pathlib.Path(path).read_text()) == []


def test_initialize_instance_history_existing_file_is_not_overwritten(history_dir):
    hm.add_history_entry("sonarr", _entry())
    before = json.loads(hm.get_history_file_path("sonarr", "Default").read_text())
    hm.initialize_instance_history("sonarr", "Default")
    after = json.loads(hm.get_history_file_path("sonarr", "Default").read_text())
    assert before == after


def test_initialize_instance_history_invalid_app_returns_none(history_dir):
    assert hm.initialize_instance_history("unknownapp", "Inst") is None

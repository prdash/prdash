"""Tests for prdash.state — UI state persistence."""

import json

import pytest

from prdash.state import (
    get_collapsed_groups,
    load_state,
    save_state,
    set_collapsed_groups,
)


class TestLoadState:
    def test_empty_when_missing(self, tmp_path):
        assert load_state(tmp_path / "nonexistent.json") == {}

    def test_loads_valid_json(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text('{"collapsed_groups": ["My PRs"]}')
        assert load_state(path) == {"collapsed_groups": ["My PRs"]}

    def test_empty_on_invalid_json(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("not json")
        assert load_state(path) == {}

    def test_empty_on_non_dict(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("[1, 2, 3]")
        assert load_state(path) == {}


class TestSaveState:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "state.json"
        save_state({"foo": "bar"}, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == {"foo": "bar"}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "state.json"
        save_state({"x": 1}, path)
        assert path.exists()

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "state.json"
        save_state({"a": 1}, path)
        save_state({"b": 2}, path)
        data = json.loads(path.read_text())
        assert data == {"b": 2}


class TestCollapsedGroups:
    def test_get_returns_empty_set_when_no_state(self, tmp_path):
        assert get_collapsed_groups(tmp_path / "missing.json") == set()

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "state.json"
        set_collapsed_groups({"My PRs", "Team Reviews"}, path)
        result = get_collapsed_groups(path)
        assert result == {"My PRs", "Team Reviews"}

    def test_set_preserves_other_state(self, tmp_path):
        path = tmp_path / "state.json"
        save_state({"other_key": "value"}, path)
        set_collapsed_groups({"My PRs"}, path)
        state = load_state(path)
        assert state["other_key"] == "value"
        assert state["collapsed_groups"] == ["My PRs"]

    def test_get_handles_non_list(self, tmp_path):
        path = tmp_path / "state.json"
        save_state({"collapsed_groups": "not a list"}, path)
        assert get_collapsed_groups(path) == set()

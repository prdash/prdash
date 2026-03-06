"""Tests for the configuration system."""

import textwrap
from pathlib import Path

import pytest

from gh_review_dashboard.config import (
    AppConfig,
    QueryGroupConfig,
    QueryGroupType,
    load_config,
)
from gh_review_dashboard.exceptions import ConfigError


def _write_toml(tmp_path: Path, content: str) -> Path:
    """Write TOML content to a temp file and return its path."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(textwrap.dedent(content))
    return config_file


class TestLoadConfigHappyPath:
    def test_full_config(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "testuser"
            team_slugs = ["team-a", "team-b"]
            poll_interval = 120

            [repo]
            org = "my-org"
            name = "my-repo"

            [[query_groups]]
            type = "direct_reviewer"
            name = "Direct"
            enabled = true

            [[query_groups]]
            type = "label"
            name = "Priority"
            labels = ["priority/high"]
            enabled = true
            """,
        )

        config = load_config(path)

        assert config.repo.org == "my-org"
        assert config.repo.name == "my-repo"
        assert config.username == "testuser"
        assert config.team_slugs == ["team-a", "team-b"]
        assert config.poll_interval == 120
        assert len(config.query_groups) == 2
        assert config.query_groups[0].type == QueryGroupType.DIRECT_REVIEWER
        assert config.query_groups[1].labels == ["priority/high"]

    def test_minimal_config_uses_defaults(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

            [repo]
            org = "org"
            name = "repo"
            """,
        )

        config = load_config(path)

        assert config.poll_interval == 300
        assert config.team_slugs == []
        assert len(config.query_groups) == 5
        group_types = [g.type for g in config.query_groups]
        assert QueryGroupType.DIRECT_REVIEWER in group_types
        assert QueryGroupType.LABEL in group_types


class TestLoadConfigErrors:
    def test_missing_file_raises_config_error(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.toml"

        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(nonexistent)

    def test_missing_required_field_repo(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"
            """,
        )

        with pytest.raises(ConfigError, match="repo"):
            load_config(path)

    def test_missing_required_field_username(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            [repo]
            org = "org"
            name = "repo"
            """,  # no username at all
        )

        with pytest.raises(ConfigError, match="username"):
            load_config(path)

    def test_invalid_query_group_type(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

            [repo]
            org = "org"
            name = "repo"

            [[query_groups]]
            type = "nonexistent"
            name = "Bad"
            """,
        )

        with pytest.raises(ConfigError):
            load_config(path)

    def test_poll_interval_too_low(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"
            poll_interval = 10

            [repo]
            org = "org"
            name = "repo"
            """,
        )

        with pytest.raises(ConfigError):
            load_config(path)


class TestQueryGroupConfig:
    def test_labels_only_valid_for_label_type(self) -> None:
        with pytest.raises(ValueError, match="labels"):
            QueryGroupConfig(
                type=QueryGroupType.DIRECT_REVIEWER,
                name="Bad",
                labels=["some-label"],
            )

    def test_label_type_with_labels(self) -> None:
        group = QueryGroupConfig(
            type=QueryGroupType.LABEL,
            name="Priority",
            labels=["priority/high", "priority/critical"],
        )
        assert group.labels == ["priority/high", "priority/critical"]

    def test_label_type_without_labels(self) -> None:
        group = QueryGroupConfig(
            type=QueryGroupType.LABEL,
            name="Labeled",
        )
        assert group.labels == []


class TestCustomQueryGroups:
    def test_custom_groups_override_defaults(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

            [repo]
            org = "org"
            name = "repo"

            [[query_groups]]
            type = "authored"
            name = "Mine"
            """,
        )

        config = load_config(path)

        assert len(config.query_groups) == 1
        assert config.query_groups[0].type == QueryGroupType.AUTHORED
        assert config.query_groups[0].name == "Mine"

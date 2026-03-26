"""Tests for the configuration system."""

import textwrap
import tomllib
from pathlib import Path

import pytest

from prdash.config import (
    AppConfig,
    QueryGroupConfig,
    QueryGroupType,
    get_org_from_repos,
    load_config,
    save_config,
)
from prdash.exceptions import ConfigError


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
            repos = ["my-org/my-repo"]

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

        assert config.repos == ["my-org/my-repo"]
        assert config.username == "testuser"
        assert config.team_slugs == ["team-a", "team-b"]
        assert config.poll_interval == 120
        # Only the 2 explicit groups from the config file
        assert len(config.query_groups) == 2
        assert config.query_groups[0].type == QueryGroupType.DIRECT_REVIEWER
        assert config.query_groups[1].labels == ["priority/high"]

    def test_minimal_config_uses_defaults(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"
            """,
        )

        config = load_config(path)

        assert config.repos == []
        assert config.poll_interval == 300
        assert config.team_slugs == []
        assert len(config.query_groups) == 7
        group_types = [g.type for g in config.query_groups]
        assert QueryGroupType.DIRECT_REVIEWER in group_types
        assert QueryGroupType.ASSIGNED in group_types
        assert QueryGroupType.LABEL in group_types
        assert QueryGroupType.READY_TO_PR in group_types

    def test_old_repo_config_migrates(self, tmp_path: Path) -> None:
        """Old-style [repo] config should be migrated to repos list."""
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

            [repo]
            org = "my-org"
            name = "my-repo"
            """,
        )

        config = load_config(path)
        assert config.repos == ["my-org/my-repo"]

    def test_empty_repos_means_all(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"
            repos = []
            """,
        )

        config = load_config(path)
        assert config.repos == []


class TestLoadConfigErrors:
    def test_missing_file_raises_config_error(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.toml"

        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(nonexistent)

    def test_missing_required_field_username(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            repos = ["org/repo"]
            """,
        )

        with pytest.raises(ConfigError, match="username"):
            load_config(path)

    def test_invalid_query_group_type(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

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
            """,
        )

        with pytest.raises(ConfigError):
            load_config(path)


class TestReposMigration:
    def test_backward_migration_dict(self) -> None:
        config = AppConfig(**{"repo": {"org": "x", "name": "y"}, "username": "u"})
        assert config.repos == ["x/y"]

    def test_repos_validation_no_slash(self) -> None:
        with pytest.raises(Exception, match="org/name"):
            AppConfig(repos=["noslash"], username="u")

    def test_repos_validation_empty_string(self) -> None:
        with pytest.raises(Exception):
            AppConfig(repos=[""], username="u")

    def test_repos_validation_valid(self) -> None:
        config = AppConfig(repos=["a/b"], username="u")
        assert config.repos == ["a/b"]

    def test_empty_repos_valid(self) -> None:
        config = AppConfig(repos=[], username="u")
        assert config.repos == []


class TestGetOrgFromRepos:
    def test_empty(self) -> None:
        assert get_org_from_repos([]) is None

    def test_single(self) -> None:
        assert get_org_from_repos(["myorg/myrepo"]) == "myorg"

    def test_multiple(self) -> None:
        assert get_org_from_repos(["org1/repo1", "org2/repo2"]) == "org1"


class TestTimeoutConfig:
    def test_default_timeout(self) -> None:
        config = AppConfig(
            repos=["org/repo"],
            username="user",
        )
        assert config.timeout == 30.0

    def test_custom_timeout(self) -> None:
        config = AppConfig(
            repos=["org/repo"],
            username="user",
            timeout=60.0,
        )
        assert config.timeout == 60.0

    def test_timeout_minimum_validation(self) -> None:
        with pytest.raises(Exception):  # Pydantic ValidationError
            AppConfig(
                repos=["org/repo"],
                username="user",
                timeout=0.5,
            )

    def test_timeout_from_toml(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"
            timeout = 45.0
            repos = ["org/repo"]
            """,
        )
        config = load_config(path)
        assert config.timeout == 45.0

    def test_timeout_round_trip(self, tmp_path: Path) -> None:
        config = AppConfig(
            repos=["org/repo"],
            username="user",
            timeout=15.0,
        )
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)
        assert loaded.timeout == 15.0


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


class TestSaveConfig:
    def _make_config(self, **overrides: object) -> AppConfig:
        defaults: dict = {
            "repos": ["test-org/test-repo"],
            "username": "testuser",
            "team_slugs": ["team-a", "team-b"],
            "poll_interval": 120,
        }
        defaults.update(overrides)
        return AppConfig(**defaults)

    def test_round_trip(self, tmp_path: Path) -> None:
        config = self._make_config()
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)

        assert loaded.repos == config.repos
        assert loaded.username == config.username
        assert loaded.team_slugs == config.team_slugs
        assert loaded.poll_interval == config.poll_interval

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "config.toml"
        config = self._make_config()
        save_config(config, path)
        assert path.exists()

    def test_output_is_valid_toml(self, tmp_path: Path) -> None:
        config = self._make_config()
        path = tmp_path / "config.toml"
        save_config(config, path)

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["username"] == "testuser"
        assert data["repos"] == ["test-org/test-repo"]

    def test_serialization_uses_repos_not_repo(self, tmp_path: Path) -> None:
        config = self._make_config()
        path = tmp_path / "config.toml"
        save_config(config, path)

        content = path.read_text()
        assert "repos = [" in content
        assert "[repo]" not in content

    def test_round_trip_with_label_groups(self, tmp_path: Path) -> None:
        groups = [
            QueryGroupConfig(
                type=QueryGroupType.LABEL,
                name="Priority",
                labels=["priority/high", "priority/critical"],
                enabled=True,
            ),
        ]
        config = self._make_config(query_groups=groups)
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)

        # Only the 1 explicit group round-trips
        assert len(loaded.query_groups) == 1
        assert loaded.query_groups[0].type == QueryGroupType.LABEL
        assert loaded.query_groups[0].labels == ["priority/high", "priority/critical"]

    def test_round_trip_empty_team_slugs(self, tmp_path: Path) -> None:
        config = self._make_config(team_slugs=[])
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)
        assert loaded.team_slugs == []

    def test_round_trip_empty_repos(self, tmp_path: Path) -> None:
        config = self._make_config(repos=[])
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)
        assert loaded.repos == []

    def test_round_trip_multiple_repos(self, tmp_path: Path) -> None:
        config = self._make_config(repos=["org/repo1", "org/repo2"])
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)
        assert loaded.repos == ["org/repo1", "org/repo2"]


class TestReadyToPrConfig:
    def test_ready_to_pr_enum_exists(self) -> None:
        assert QueryGroupType.READY_TO_PR == "ready_to_pr"

    def test_default_groups_include_ready_to_pr_first(self) -> None:
        from prdash.config import DEFAULT_QUERY_GROUPS
        assert DEFAULT_QUERY_GROUPS[0].type == QueryGroupType.READY_TO_PR
        assert DEFAULT_QUERY_GROUPS[0].name == "Ready to PR"

    def test_round_trip_ready_to_pr(self, tmp_path: Path) -> None:
        groups = [
            QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR"),
        ]
        config = AppConfig(repos=["org/repo"], username="user", query_groups=groups)
        path = tmp_path / "config.toml"
        save_config(config, path)
        loaded = load_config(path)
        assert loaded.query_groups[0].type == QueryGroupType.READY_TO_PR
        assert loaded.query_groups[0].name == "Ready to PR"


class TestCustomQueryGroups:
    def test_custom_groups_override_defaults(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """\
            username = "user"

            [[query_groups]]
            type = "authored"
            name = "Mine"
            """,
        )

        config = load_config(path)

        # Only the 1 explicit group — no backfill
        assert len(config.query_groups) == 1
        assert config.query_groups[0].type == QueryGroupType.AUTHORED
        assert config.query_groups[0].name == "Mine"

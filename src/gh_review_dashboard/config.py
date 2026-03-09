"""TOML-based configuration loading and Pydantic models."""

import os
import tempfile
import tomllib
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from gh_review_dashboard.exceptions import ConfigError

CONFIG_DIR: Path = Path.home() / ".config" / "gh-review-dashboard"
CONFIG_FILE: Path = CONFIG_DIR / "config.toml"


class QueryGroupType(str, Enum):
    """Type of PR query group."""

    DIRECT_REVIEWER = "direct_reviewer"
    TEAM_REVIEWER = "team_reviewer"
    MENTIONED = "mentioned"
    AUTHORED = "authored"
    LABEL = "label"


class QueryGroupConfig(BaseModel):
    """Configuration for a single PR query group."""

    type: QueryGroupType
    name: str
    labels: list[str] = Field(default_factory=list)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_labels(self) -> "QueryGroupConfig":
        if self.labels and self.type != QueryGroupType.LABEL:
            raise ValueError("'labels' can only be set when type is 'label'")
        return self


class RepoConfig(BaseModel):
    """GitHub repository coordinates."""

    org: str
    name: str


DEFAULT_QUERY_GROUPS: list[QueryGroupConfig] = [
    QueryGroupConfig(type=QueryGroupType.AUTHORED, name="My PRs"),
    QueryGroupConfig(type=QueryGroupType.MENTIONED, name="Mentioned/Involved"),
    QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Requested Reviewer"),
    QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team Reviewer"),
    QueryGroupConfig(
        type=QueryGroupType.LABEL, name="Labeled", labels=[], enabled=False
    ),
]


class AppConfig(BaseModel):
    """Top-level application configuration."""

    repo: RepoConfig
    username: str
    team_slugs: list[str] = Field(default_factory=list)
    poll_interval: int = Field(default=300, ge=30)
    timeout: float = Field(default=30.0, ge=1.0)
    query_groups: list[QueryGroupConfig] = Field(
        default_factory=lambda: list(DEFAULT_QUERY_GROUPS)
    )


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate configuration from a TOML file.

    Args:
        path: Path to the config file. Defaults to ~/.config/gh-review-dashboard/config.toml.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigError: If the file is missing or contains invalid configuration.
    """
    config_path = path or CONFIG_FILE

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}\n"
            f"Create it with at least:\n\n"
            f"  [repo]\n"
            f'  org = "your-org"\n'
            f'  name = "your-repo"\n\n'
            f'  username = "your-github-username"\n'
        )

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    try:
        return AppConfig(**data)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration in {config_path}:\n{e}") from e


def _serialize_config_toml(config: AppConfig) -> str:
    """Serialize an AppConfig to TOML-formatted string."""
    lines: list[str] = []

    lines.append(f'username = "{config.username}"')
    if config.team_slugs:
        slugs = ", ".join(f'"{s}"' for s in config.team_slugs)
        lines.append(f"team_slugs = [{slugs}]")
    else:
        lines.append("team_slugs = []")
    lines.append(f"poll_interval = {config.poll_interval}")
    lines.append(f"timeout = {config.timeout}")

    lines.append("")
    lines.append("[repo]")
    lines.append(f'org = "{config.repo.org}"')
    lines.append(f'name = "{config.repo.name}"')

    for group in config.query_groups:
        lines.append("")
        lines.append("[[query_groups]]")
        lines.append(f'type = "{group.type.value}"')
        lines.append(f'name = "{group.name}"')
        if group.labels:
            labels = ", ".join(f'"{l}"' for l in group.labels)
            lines.append(f"labels = [{labels}]")
        lines.append(f"enabled = {'true' if group.enabled else 'false'}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save configuration to a TOML file atomically.

    Creates parent directories if needed. Writes to a temp file
    then atomically replaces the target.

    Args:
        config: The AppConfig to save.
        path: Target path. Defaults to CONFIG_FILE.
    """
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)

    content = _serialize_config_toml(config)

    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent, suffix=".tmp", prefix=".config_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, config_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

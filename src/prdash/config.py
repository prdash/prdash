"""TOML-based configuration loading and Pydantic models."""

import os
import re
import tempfile
import tomllib
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from prdash.exceptions import ConfigError

CONFIG_DIR: Path = Path.home() / ".config" / "prdash"
CONFIG_FILE: Path = CONFIG_DIR / "config.toml"

_REPO_SLUG_RE = re.compile(r"^[^/]+/[^/]+$")


class QueryGroupType(str, Enum):
    """Type of PR query group."""

    DIRECT_REVIEWER = "direct_reviewer"
    TEAM_REVIEWER = "team_reviewer"
    REVIEWED_BY = "reviewed_by"
    MENTIONED = "mentioned"
    AUTHORED = "authored"
    ASSIGNED = "assigned"
    LABEL = "label"
    READY_TO_PR = "ready_to_pr"


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


DEFAULT_QUERY_GROUPS: list[QueryGroupConfig] = [
    QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR"),
    QueryGroupConfig(type=QueryGroupType.AUTHORED, name="My PRs"),
    QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Requested Reviewer"),
    QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team Reviewer"),
    QueryGroupConfig(type=QueryGroupType.REVIEWED_BY, name="Reviewed by Me"),
    QueryGroupConfig(type=QueryGroupType.ASSIGNED, name="Assigned to Me"),
    QueryGroupConfig(type=QueryGroupType.MENTIONED, name="Mentioned/Involved"),
    QueryGroupConfig(
        type=QueryGroupType.LABEL, name="Labeled", labels=[], enabled=False
    ),
]


def get_org_from_repos(repos: list[str]) -> str | None:
    """Return the org from the first repo slug, or None if repos is empty."""
    if not repos:
        return None
    return repos[0].split("/")[0]


class AppConfig(BaseModel):
    """Top-level application configuration."""

    repos: list[str] = Field(default_factory=list)
    username: str
    team_slugs: list[str] = Field(default_factory=list)
    poll_interval: int = Field(default=300, ge=30)
    timeout: float = Field(default=30.0, ge=1.0)
    theme: str = "textual-dark"
    nerd_font: bool = False
    query_groups: list[QueryGroupConfig] = Field(
        default_factory=lambda: list(DEFAULT_QUERY_GROUPS)
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_repo_to_repos(cls, data: dict) -> dict:
        """Migrate old-style `repo` config to new `repos` list."""
        if not isinstance(data, dict):
            return data
        if "repo" in data:
            repo = data.pop("repo")
            if isinstance(repo, dict):
                org = repo.get("org", "")
                name = repo.get("name", "")
            elif hasattr(repo, "org"):
                org = repo.org
                name = repo.name
            else:
                return data
            if org and name:
                data.setdefault("repos", [f"{org}/{name}"])
        return data

    @field_validator("repos")
    @classmethod
    def validate_repos(cls, v: list[str]) -> list[str]:
        for entry in v:
            if not _REPO_SLUG_RE.match(entry):
                raise ValueError(
                    f"Invalid repo slug '{entry}': must be 'org/name'"
                )
        return v


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate configuration from a TOML file.

    Args:
        path: Path to the config file. Defaults to ~/.config/prdash/config.toml.

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
            f'  username = "your-github-username"\n'
            f'  repos = ["your-org/your-repo"]  # optional, empty = all repos\n'
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
    if config.theme != "textual-dark":
        lines.append(f'theme = "{config.theme}"')
    if config.nerd_font:
        lines.append("nerd_font = true")

    if config.repos:
        repos = ", ".join(f'"{r}"' for r in config.repos)
        lines.append(f"repos = [{repos}]")
    else:
        lines.append("repos = []")

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

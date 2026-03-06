# Data Models Reference

## Pydantic v2 Patterns

This project uses Pydantic v2 (`BaseModel` from `pydantic`). Key differences from v1:
- `model_validator` replaces `root_validator`
- `field_validator` replaces `validator`
- `model_dump()` replaces `dict()`
- Use `Field()` for defaults, descriptions, aliases

## Config Models

```python
from pydantic import BaseModel, Field
import tomllib
from pathlib import Path
from enum import Enum

class QueryGroupType(str, Enum):
    """str mixin allows direct TOML string matching."""
    DIRECT_REVIEWER = "direct_reviewer"
    TEAM_REVIEWER = "team_reviewer"
    MENTIONED = "mentioned"
    AUTHORED = "authored"
    LABEL = "label"

class QueryGroup(BaseModel):
    name: str
    type: QueryGroupType
    enabled: bool = True
    labels: list[str] = Field(default_factory=list)  # Only for LABEL type

class AppConfig(BaseModel):
    github_username: str
    repository: str                           # "org/repo" format
    team_slugs: list[str] = Field(default_factory=list)
    poll_interval: int = Field(default=300, ge=30)  # seconds
    query_groups: list[QueryGroup] = Field(default_factory=list)

def load_config(path: Path) -> AppConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return AppConfig(**data)
```

- Wrap `AppConfig(...)` in try/except `ValidationError` — raise `ConfigError` with user-friendly message
- Provide sensible defaults for query_groups when list is empty

## PR Data Models

```python
from datetime import datetime, UTC
from pydantic import BaseModel, computed_field

class Reviewer(BaseModel, frozen=True):
    login: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, PENDING

class CheckRun(BaseModel, frozen=True):
    name: str
    status: str       # COMPLETED, IN_PROGRESS, QUEUED
    conclusion: str | None  # SUCCESS, FAILURE, NEUTRAL, etc.

class TimelineEvent(BaseModel, frozen=True):
    type: str         # REVIEW, COMMENT, FORCE_PUSH, MERGED
    author: str
    created_at: datetime
    body: str | None = None

class PullRequest(BaseModel, frozen=True):
    number: int
    title: str
    url: str
    author: str
    created_at: datetime
    labels: list[str] = Field(default_factory=list)
    reviewers: list[Reviewer] = Field(default_factory=list)
    check_runs: list[CheckRun] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)

    @computed_field
    @property
    def age_display(self) -> str:
        """Human-readable age like '2h', '3d', '1w'."""
        ...

    @computed_field
    @property
    def ci_status(self) -> str:
        """Aggregate CI status: pass/fail/pending/none."""
        if not self.check_runs:
            return "none"
        if any(c.conclusion == "FAILURE" for c in self.check_runs):
            return "fail"
        if all(c.conclusion == "SUCCESS" for c in self.check_runs):
            return "pass"
        return "pending"

    @computed_field
    @property
    def review_status(self) -> str:
        """Aggregate review status: approved/changes_requested/pending/none."""
        if not self.reviewers:
            return "none"
        states = {r.state for r in self.reviewers}
        if "CHANGES_REQUESTED" in states:
            return "changes_requested"
        if "APPROVED" in states and "PENDING" not in states:
            return "approved"
        return "pending"
```

## Immutability

Use `frozen=True` on data models (PullRequest, Reviewer, CheckRun, TimelineEvent).
Config models are mutable since they may be updated at runtime.

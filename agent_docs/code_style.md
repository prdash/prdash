# Code Style Guide

## Module Template

```python
"""Module description — one line summary.

Extended description if needed.
"""

# Standard library
from datetime import datetime
from pathlib import Path

# Third-party
import httpx
from pydantic import BaseModel
from textual.app import App

# Local
from gh_review_dashboard.config import AppConfig
from gh_review_dashboard.models import PullRequest
```

Import order: stdlib, blank line, third-party, blank line, local.

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Modules | snake_case | `github_client.py` |
| Functions | snake_case | `fetch_pull_requests()` |
| Classes | PascalCase | `GitHubClient`, `PRListWidget` |
| Constants | UPPER_SNAKE | `DEFAULT_POLL_INTERVAL` |
| Type aliases | PascalCase | `PRGroup = dict[str, list[PullRequest]]` |
| Private | leading underscore | `_parse_response()` |
| Test files | `test_` prefix | `test_github_client.py` |
| Test functions | `test_` prefix | `test_fetch_returns_prs()` |

## Error Hierarchy

```python
class DashboardError(Exception):
    """Base exception for all dashboard errors."""

class AuthError(DashboardError):
    """GitHub authentication failed (gh CLI missing, token expired)."""

class ConfigError(DashboardError):
    """Configuration loading or validation failed."""

class GitHubAPIError(DashboardError):
    """GitHub API request failed (network, rate limit, query error)."""
```

- Always inherit from `DashboardError`
- Include context in error messages: what failed and why
- Catch specific exceptions, not bare `except:`

## Dependency Injection

```python
# Good: dependencies as constructor args
class GitHubClient:
    def __init__(self, http_client: httpx.AsyncClient, config: AppConfig) -> None:
        self._client = http_client
        self._config = config

# Good: app wires dependencies at startup
app = DashboardApp(config=config, github_client=client)

# Bad: importing and constructing internally
class GitHubClient:
    def __init__(self):
        self._client = httpx.AsyncClient(...)  # Hard to test
```

- Pass all external dependencies (HTTP clients, config, tokens) as constructor args
- Wire everything together in the entry point (`__main__.py`)
- This makes every class independently testable with mocks

## Async Conventions

- All I/O functions are `async def` — never use blocking I/O in async context
- Use `await` for single operations, `asyncio.gather()` for parallel
- Textual workers (`@work`) for background tasks that update UI
- Exception: `subprocess.run` for `gh auth token` is acceptable (one-time, fast)

## File Size Guidelines

- **Soft limit: ~300 lines** per module
- One primary class per file (especially widgets)
- If a module exceeds 300 lines, consider splitting:
  - `github_client.py` -> `github_client.py` + `graphql_queries.py`
  - `models.py` -> `models.py` + `parsers.py`
- Test files can be longer since test functions are independent

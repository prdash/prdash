# Testing Guide

## Directory Structure

Tests mirror the `src/` layout:
```
tests/
  test_config.py          # Tests for config.py
  test_github_client.py   # Tests for github_client.py
  test_models.py          # Tests for models.py
  test_auth.py            # Tests for auth/token extraction
  test_app.py             # Tests for Textual app
  conftest.py             # Shared fixtures
```

## Test File Naming

- File: `tests/test_{module}.py`
- Functions: `test_{method}_{scenario}_{expected}` or `test_{behavior}`
- Classes (optional grouping): `class TestClassName:`

## Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_pull_requests():
    client = GitHubClient(token="fake", org="org", repo="repo")
    # ... mock and test
```

## Mocking httpx (with respx or unittest.mock)

```python
# Option A: respx library (preferred for httpx)
import respx
from httpx import Response

@respx.mock
async def test_graphql_query():
    respx.post("https://api.github.com/graphql").mock(
        return_value=Response(200, json={"data": {...}})
    )
    result = await client.fetch_prs(group)
    assert len(result) == 2

# Option B: unittest.mock
from unittest.mock import AsyncMock, patch

async def test_fetch_with_mock():
    mock_client = AsyncMock()
    mock_client.post.return_value = Response(200, json={...})
    github = GitHubClient(http_client=mock_client, ...)
    result = await github.fetch_prs(group)
```

## Mocking subprocess (gh CLI auth)

```python
from unittest.mock import patch, MagicMock

def test_get_token_from_gh_cli():
    result = MagicMock()
    result.stdout = "ghp_xxxxxxxxxxxx\n"
    result.returncode = 0
    with patch("subprocess.run", return_value=result) as mock_run:
        token = get_gh_token()
        assert token == "ghp_xxxxxxxxxxxx"
        mock_run.assert_called_once()
```

## Filesystem Fixtures (tmp_path)

```python
def test_load_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
    [general]
    github_username = "testuser"
    repository = "org/repo"
    ''')
    config = load_config(config_file)
    assert config.github_username == "testuser"
```

## Pydantic Model Tests

```python
def test_pull_request_review_status():
    """Test computed review status from reviewer data."""
    pr = PullRequest(
        title="Fix bug", author="alice",
        reviewers=[Reviewer(login="bob", state="APPROVED")],
        # ... other required fields
    )
    assert pr.review_status == "approved"

def test_config_validation_error():
    with pytest.raises(ValidationError):
        AppConfig(repository="invalid")  # missing required fields
```

## Textual Pilot Testing

```python
import pytest
from textual.testing import AppTest

@pytest.mark.asyncio
async def test_app_launches():
    async with AppTest(DashboardApp()).run_test() as pilot:
        # Verify initial state
        assert pilot.app.query_one("#pr-list") is not None

@pytest.mark.asyncio
async def test_navigation():
    async with AppTest(DashboardApp()).run_test() as pilot:
        await pilot.press("j")  # Move down
        await pilot.press("enter")  # Open PR
```

## Shared Fixtures (conftest.py)

```python
@pytest.fixture
def sample_pull_request():
    return PullRequest(
        title="Add feature", author="alice", number=42,
        url="https://github.com/org/repo/pull/42",
        created_at=datetime.now(UTC), ...
    )

@pytest.fixture
def sample_config(tmp_path):
    return AppConfig(
        github_username="testuser", repository="org/repo",
        team_slugs=["my-team"], poll_interval=300,
    )

@pytest.fixture
def mock_github_client():
    client = AsyncMock(spec=GitHubClient)
    client.fetch_prs.return_value = [sample_pull_request()]
    return client
```

## What NOT to Test

- Pydantic's own validation logic (trust the framework)
- Textual's built-in widget behavior (focus, scroll, render)
- Real HTTP calls to GitHub API
- Private methods directly — test through public interface
- Exact CSS rendering — test widget presence and data, not pixels

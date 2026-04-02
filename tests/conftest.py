"""Shared test fixtures."""

from datetime import UTC, datetime, timedelta

import pytest

from prdash.models import (
    CheckRun,
    PullRequest,
    QueryGroupResult,
    Reviewer,
    TimelineEvent,
)


@pytest.fixture(autouse=True)
def _clean_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent argparse from seeing pytest's arguments."""
    monkeypatch.setattr("sys.argv", ["prdash"])


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from reading/writing the real state file."""
    monkeypatch.setattr("prdash.state.STATE_FILE", None)
    monkeypatch.setattr("prdash.widgets.pr_list.get_collapsed_groups", lambda path=None: set())
    monkeypatch.setattr("prdash.widgets.pr_list.set_collapsed_groups", lambda groups, path=None: None)


@pytest.fixture
def sample_pr() -> PullRequest:
    return PullRequest(
        id="PR_1",
        number=42,
        title="Fix auth token refresh",
        author="alice",
        url="https://github.com/org/repo/pull/42",
        created_at=datetime.now(UTC) - timedelta(days=2),
        repo_slug="test-org/test-repo",
        body="This PR fixes the auth token refresh logic.",
        labels=["bug", "auth"],
        reviewers=[
            Reviewer(login="bob", state="APPROVED"),
            Reviewer(login="carol", state="PENDING"),
        ],
        checks=[
            CheckRun(name="unit-tests", status="COMPLETED", conclusion="SUCCESS"),
            CheckRun(name="lint", status="COMPLETED", conclusion="FAILURE"),
        ],
        timeline_events=[
            TimelineEvent(
                type="IssueComment",
                author="alice",
                created_at=datetime.now(UTC) - timedelta(hours=6),
                body="Ready for review.",
            ),
            TimelineEvent(
                type="PullRequestReview",
                author="bob",
                created_at=datetime.now(UTC) - timedelta(hours=3),
                body="LGTM",
            ),
            TimelineEvent(
                type="HeadRefForcePushed",
                author="alice",
                created_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ],
    )


@pytest.fixture
def sample_pr_minimal() -> PullRequest:
    return PullRequest(
        id="PR_2",
        number=99,
        title="Add README",
        author="bob",
        url="https://github.com/org/repo/pull/99",
        created_at=datetime.now(UTC) - timedelta(hours=5),
        repo_slug="test-org/test-repo",
    )


@pytest.fixture
def sample_groups(sample_pr: PullRequest, sample_pr_minimal: PullRequest) -> list[QueryGroupResult]:
    return [
        QueryGroupResult(
            group_name="Review Requested",
            group_type="review_requested",
            pull_requests=[sample_pr, sample_pr_minimal],
        ),
        QueryGroupResult(
            group_name="Team Reviews",
            group_type="team_review",
            pull_requests=[],
        ),
        QueryGroupResult(
            group_name="My PRs",
            group_type="authored",
            pull_requests=[sample_pr_minimal],
        ),
    ]

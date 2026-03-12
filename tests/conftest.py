"""Shared test fixtures."""

from datetime import UTC, datetime, timedelta

import pytest

from gh_review_dashboard.models import (
    CheckRun,
    PullRequest,
    QueryGroupResult,
    Reviewer,
    TimelineEvent,
)


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

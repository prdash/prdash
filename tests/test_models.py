"""Tests for gh_review_dashboard.models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gh_review_dashboard.models import (
    CheckRun,
    PullRequest,
    Reviewer,
    TimelineEvent,
    parse_pr_node,
    parse_search_results,
)


def _make_pr(**kwargs) -> PullRequest:
    """Helper to create a PullRequest with sensible defaults."""
    defaults = {
        "id": "PR_1",
        "number": 1,
        "title": "Test PR",
        "author": "alice",
        "url": "https://github.com/org/repo/pull/1",
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return PullRequest(**defaults)


# --- CI Status ---


class TestPullRequestCiStatus:
    def test_no_checks(self) -> None:
        pr = _make_pr(checks=[])
        assert pr.ci_status == "none"

    def test_all_success(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="build", status="COMPLETED", conclusion="SUCCESS"),
                CheckRun(name="lint", status="COMPLETED", conclusion="SUCCESS"),
            ]
        )
        assert pr.ci_status == "passing"

    def test_any_failure(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="build", status="COMPLETED", conclusion="SUCCESS"),
                CheckRun(name="test", status="COMPLETED", conclusion="FAILURE"),
            ]
        )
        assert pr.ci_status == "failing"

    def test_mixed_pending(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="build", status="COMPLETED", conclusion="SUCCESS"),
                CheckRun(name="test", status="IN_PROGRESS", conclusion=None),
            ]
        )
        assert pr.ci_status == "pending"

    def test_null_conclusion_is_pending(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="QUEUED", conclusion=None)]
        )
        assert pr.ci_status == "pending"


# --- Review Status ---


class TestPullRequestReviewStatus:
    def test_no_reviewers(self) -> None:
        pr = _make_pr(reviewers=[])
        assert pr.review_status == "none"

    def test_all_approved(self) -> None:
        pr = _make_pr(
            reviewers=[
                Reviewer(login="bob", state="APPROVED"),
                Reviewer(login="carol", state="APPROVED"),
            ]
        )
        assert pr.review_status == "approved"

    def test_changes_requested_overrides(self) -> None:
        pr = _make_pr(
            reviewers=[
                Reviewer(login="bob", state="APPROVED"),
                Reviewer(login="carol", state="CHANGES_REQUESTED"),
            ]
        )
        assert pr.review_status == "changes_requested"

    def test_pending_plus_approved(self) -> None:
        pr = _make_pr(
            reviewers=[
                Reviewer(login="bob", state="APPROVED"),
                Reviewer(login="carol", state="PENDING"),
            ]
        )
        assert pr.review_status == "pending"

    def test_only_pending(self) -> None:
        pr = _make_pr(reviewers=[Reviewer(login="bob", state="PENDING")])
        assert pr.review_status == "pending"


# --- Age Display ---


class TestPullRequestAgeDisplay:
    def test_minutes(self) -> None:
        pr = _make_pr(created_at=datetime.now(UTC) - timedelta(minutes=30))
        assert pr.age_display == "30m"

    def test_hours(self) -> None:
        pr = _make_pr(created_at=datetime.now(UTC) - timedelta(hours=5))
        assert pr.age_display == "5h"

    def test_days(self) -> None:
        pr = _make_pr(created_at=datetime.now(UTC) - timedelta(days=3))
        assert pr.age_display == "3d"

    def test_weeks(self) -> None:
        pr = _make_pr(created_at=datetime.now(UTC) - timedelta(weeks=2))
        assert pr.age_display == "2w"

    def test_zero_minutes_shows_1m(self) -> None:
        pr = _make_pr(created_at=datetime.now(UTC) - timedelta(seconds=10))
        assert pr.age_display == "1m"


# --- parse_pr_node ---


class TestParsePrNode:
    def _sample_node(self, **overrides) -> dict:
        node = {
            "id": "PR_abc",
            "number": 42,
            "title": "Add feature",
            "url": "https://github.com/org/repo/pull/42",
            "createdAt": "2025-01-15T10:00:00Z",
            "body": "PR body text",
            "author": {"login": "alice"},
            "labels": {"nodes": [{"name": "bug"}, {"name": "urgent"}]},
            "reviewRequests": {
                "nodes": [{"requestedReviewer": {"login": "bob"}}]
            },
            "reviews": {
                "nodes": [{"author": {"login": "carol"}, "state": "APPROVED"}]
            },
            "commits": {
                "nodes": [
                    {
                        "commit": {
                            "statusCheckRollup": {
                                "contexts": {
                                    "nodes": [
                                        {
                                            "name": "ci/build",
                                            "status": "COMPLETED",
                                            "conclusion": "SUCCESS",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            },
            "timelineItems": {
                "nodes": [
                    {
                        "__typename": "IssueComment",
                        "author": {"login": "dave"},
                        "createdAt": "2025-01-15T12:00:00Z",
                        "body": "Looks good",
                    }
                ]
            },
        }
        node.update(overrides)
        return node

    def test_full_node(self) -> None:
        pr = parse_pr_node(self._sample_node())
        assert pr.id == "PR_abc"
        assert pr.number == 42
        assert pr.title == "Add feature"
        assert pr.author == "alice"
        assert pr.labels == ["bug", "urgent"]
        assert len(pr.reviewers) == 2  # bob (PENDING) + carol (APPROVED)
        assert len(pr.checks) == 1
        assert pr.checks[0].name == "ci/build"
        assert len(pr.timeline_events) == 1
        assert pr.timeline_events[0].type == "IssueComment"

    def test_null_author_becomes_ghost(self) -> None:
        pr = parse_pr_node(self._sample_node(author=None))
        assert pr.author == "ghost"

    def test_empty_checks(self) -> None:
        node = self._sample_node(
            commits={"nodes": [{"commit": {"statusCheckRollup": None}}]}
        )
        pr = parse_pr_node(node)
        assert pr.checks == []

    def test_timeline_force_push(self) -> None:
        node = self._sample_node(
            timelineItems={
                "nodes": [
                    {
                        "__typename": "HeadRefForcePushedEvent",
                        "actor": {"login": "alice"},
                        "createdAt": "2025-01-15T14:00:00Z",
                    }
                ]
            }
        )
        pr = parse_pr_node(node)
        assert len(pr.timeline_events) == 1
        assert pr.timeline_events[0].type == "HeadRefForcePushed"
        assert pr.timeline_events[0].author == "alice"

    def test_timeline_null_author(self) -> None:
        node = self._sample_node(
            timelineItems={
                "nodes": [
                    {
                        "__typename": "IssueComment",
                        "author": None,
                        "createdAt": "2025-01-15T14:00:00Z",
                        "body": "auto comment",
                    }
                ]
            }
        )
        pr = parse_pr_node(node)
        assert pr.timeline_events[0].author == "ghost"

    def test_reviewer_deduplication(self) -> None:
        """Latest review state should override pending request."""
        node = self._sample_node(
            reviewRequests={"nodes": [{"requestedReviewer": {"login": "bob"}}]},
            reviews={
                "nodes": [{"author": {"login": "bob"}, "state": "APPROVED"}]
            },
        )
        pr = parse_pr_node(node)
        bob = next(r for r in pr.reviewers if r.login == "bob")
        assert bob.state == "APPROVED"

    def test_status_context_check(self) -> None:
        """StatusContext nodes should be parsed as CheckRuns."""
        node = self._sample_node(
            commits={
                "nodes": [
                    {
                        "commit": {
                            "statusCheckRollup": {
                                "contexts": {
                                    "nodes": [
                                        {"context": "ci/external", "state": "SUCCESS"}
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        )
        pr = parse_pr_node(node)
        assert len(pr.checks) == 1
        assert pr.checks[0].name == "ci/external"
        assert pr.checks[0].conclusion == "SUCCESS"


# --- parse_search_results ---


class TestParseSearchResults:
    def test_with_pagination(self) -> None:
        data = {
            "data": {
                "search": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor123"},
                    "nodes": [
                        {
                            "id": "PR_1",
                            "number": 1,
                            "title": "PR 1",
                            "url": "https://github.com/org/repo/pull/1",
                            "createdAt": "2025-01-15T10:00:00Z",
                            "body": None,
                            "author": {"login": "alice"},
                            "labels": {"nodes": []},
                            "reviewRequests": {"nodes": []},
                            "reviews": {"nodes": []},
                            "commits": {"nodes": []},
                            "timelineItems": {"nodes": []},
                        }
                    ],
                }
            }
        }
        prs, has_next, cursor = parse_search_results(data)
        assert len(prs) == 1
        assert has_next is True
        assert cursor == "cursor123"

    def test_empty_results(self) -> None:
        data = {
            "data": {
                "search": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [],
                }
            }
        }
        prs, has_next, cursor = parse_search_results(data)
        assert prs == []
        assert has_next is False
        assert cursor is None

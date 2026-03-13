"""Tests for gh_review_dashboard.models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gh_review_dashboard.models import (
    CandidateBranch,
    CheckRun,
    PullRequest,
    QueryGroupResult,
    Reviewer,
    TimelineEvent,
    _format_age,
    deduplicate_groups,
    parse_pr_node,
    parse_refs_results,
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


# --- is_approved_by ---


class TestIsApprovedBy:
    def test_approved_reviewer(self) -> None:
        pr = _make_pr(reviewers=[Reviewer(login="bob", state="APPROVED")])
        assert pr.is_approved_by("bob") is True

    def test_pending_reviewer(self) -> None:
        pr = _make_pr(reviewers=[Reviewer(login="bob", state="PENDING")])
        assert pr.is_approved_by("bob") is False

    def test_missing_reviewer(self) -> None:
        pr = _make_pr(reviewers=[Reviewer(login="carol", state="APPROVED")])
        assert pr.is_approved_by("bob") is False

    def test_no_reviewers(self) -> None:
        pr = _make_pr(reviewers=[])
        assert pr.is_approved_by("bob") is False

    def test_changes_requested_not_approved(self) -> None:
        pr = _make_pr(reviewers=[Reviewer(login="bob", state="CHANGES_REQUESTED")])
        assert pr.is_approved_by("bob") is False


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
            "repository": {"nameWithOwner": "org/repo"},
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
        assert pr.repo_slug == "org/repo"
        assert pr.labels == ["bug", "urgent"]
        assert len(pr.reviewers) == 2  # bob (PENDING) + carol (APPROVED)
        assert len(pr.checks) == 1
        assert pr.checks[0].name == "ci/build"
        assert len(pr.timeline_events) == 1
        assert pr.timeline_events[0].type == "IssueComment"

    def test_repo_slug_missing_repository(self) -> None:
        node = self._sample_node()
        del node["repository"]
        pr = parse_pr_node(node)
        assert pr.repo_slug == ""

    def test_repo_slug_null_repository(self) -> None:
        pr = parse_pr_node(self._sample_node(repository=None))
        assert pr.repo_slug == ""

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


# --- deduplicate_groups ---


class TestDeduplicateGroups:
    def _make_group(self, name: str, pr_ids: list[str]) -> QueryGroupResult:
        prs = [_make_pr(id=pid, number=i) for i, pid in enumerate(pr_ids, 1)]
        return QueryGroupResult(group_name=name, group_type="test", pull_requests=prs)

    def test_no_overlap(self) -> None:
        groups = [
            self._make_group("A", ["PR_1", "PR_2"]),
            self._make_group("B", ["PR_3", "PR_4"]),
        ]
        result = deduplicate_groups(groups)
        assert [pr.id for pr in result[0].pull_requests] == ["PR_1", "PR_2"]
        assert [pr.id for pr in result[1].pull_requests] == ["PR_3", "PR_4"]

    def test_partial_overlap(self) -> None:
        groups = [
            self._make_group("A", ["PR_1", "PR_2"]),
            self._make_group("B", ["PR_2", "PR_3"]),
            self._make_group("C", ["PR_1", "PR_4"]),
        ]
        result = deduplicate_groups(groups)
        assert [pr.id for pr in result[0].pull_requests] == ["PR_1", "PR_2"]
        assert [pr.id for pr in result[1].pull_requests] == ["PR_3"]
        assert [pr.id for pr in result[2].pull_requests] == ["PR_4"]

    def test_full_overlap_second_group_empty(self) -> None:
        groups = [
            self._make_group("A", ["PR_1", "PR_2"]),
            self._make_group("B", ["PR_1", "PR_2"]),
        ]
        result = deduplicate_groups(groups)
        assert [pr.id for pr in result[0].pull_requests] == ["PR_1", "PR_2"]
        assert result[1].pull_requests == []

    def test_empty_groups_pass_through(self) -> None:
        groups = [
            self._make_group("A", ["PR_1"]),
            self._make_group("B", []),
            self._make_group("C", ["PR_2"]),
        ]
        result = deduplicate_groups(groups)
        assert len(result) == 3
        assert result[1].pull_requests == []
        assert [pr.id for pr in result[2].pull_requests] == ["PR_2"]

    def test_single_group_noop(self) -> None:
        groups = [self._make_group("A", ["PR_1", "PR_2", "PR_3"])]
        result = deduplicate_groups(groups)
        assert [pr.id for pr in result[0].pull_requests] == ["PR_1", "PR_2", "PR_3"]

    def test_order_matters(self) -> None:
        """Same PRs in different group order should yield different assignment."""
        groups_ab = [
            self._make_group("A", ["PR_1", "PR_2"]),
            self._make_group("B", ["PR_1", "PR_2"]),
        ]
        groups_ba = [
            self._make_group("B", ["PR_1", "PR_2"]),
            self._make_group("A", ["PR_1", "PR_2"]),
        ]
        result_ab = deduplicate_groups(groups_ab)
        result_ba = deduplicate_groups(groups_ba)
        # First group gets all PRs, second gets none
        assert [pr.id for pr in result_ab[0].pull_requests] == ["PR_1", "PR_2"]
        assert result_ab[1].pull_requests == []
        assert [pr.id for pr in result_ba[0].pull_requests] == ["PR_1", "PR_2"]
        assert result_ba[1].pull_requests == []

    def test_does_not_mutate_originals(self) -> None:
        original = self._make_group("A", ["PR_1", "PR_2"])
        groups = [original, self._make_group("B", ["PR_1"])]
        deduplicate_groups(groups)
        assert len(original.pull_requests) == 2

    def test_branches_pass_through(self) -> None:
        branch = CandidateBranch(
            name="feat/x",
            repo_slug="org/repo",
            last_commit_date=datetime.now(UTC),
            compare_url="https://github.com/org/repo/compare/feat%2Fx?expand=1",
        )
        groups = [
            QueryGroupResult(
                group_name="A",
                group_type="test",
                pull_requests=[_make_pr(id="PR_1", number=1)],
                branches=[branch],
            ),
        ]
        result = deduplicate_groups(groups)
        assert result[0].branches == [branch]


# --- _format_age ---


class TestFormatAge:
    def test_minutes(self) -> None:
        assert _format_age(datetime.now(UTC) - timedelta(minutes=30)) == "30m"

    def test_hours(self) -> None:
        assert _format_age(datetime.now(UTC) - timedelta(hours=5)) == "5h"

    def test_days(self) -> None:
        assert _format_age(datetime.now(UTC) - timedelta(days=3)) == "3d"

    def test_weeks(self) -> None:
        assert _format_age(datetime.now(UTC) - timedelta(weeks=2)) == "2w"

    def test_zero_shows_1m(self) -> None:
        assert _format_age(datetime.now(UTC) - timedelta(seconds=10)) == "1m"


# --- CandidateBranch ---


class TestCandidateBranch:
    def test_age_display(self) -> None:
        branch = CandidateBranch(
            name="feat/foo",
            repo_slug="org/repo",
            last_commit_date=datetime.now(UTC) - timedelta(hours=3),
            compare_url="https://github.com/org/repo/compare/feat%2Ffoo?expand=1",
        )
        assert branch.age_display == "3h"


# --- parse_refs_results ---


class TestParseRefsResults:
    def _make_refs_data(self, nodes: list[dict], default_branch: str = "main") -> dict:
        return {
            "data": {
                "repository": {
                    "defaultBranchRef": {"name": default_branch},
                    "refs": {"nodes": nodes},
                }
            }
        }

    def _make_ref_node(
        self,
        name: str = "feat/test",
        login: str = "testuser",
        committed_date: str | None = None,
        open_prs: int = 0,
        author_user: dict | None = None,
    ) -> dict:
        if committed_date is None:
            committed_date = datetime.now(UTC).isoformat()
        if author_user is None:
            author_user = {"login": login}
        return {
            "name": name,
            "target": {
                "committedDate": committed_date,
                "author": {"user": author_user},
            },
            "associatedPullRequests": {"totalCount": open_prs},
        }

    def test_basic_candidate(self) -> None:
        node = self._make_ref_node(name="feat/test", login="testuser")
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert len(result) == 1
        assert result[0].name == "feat/test"
        assert result[0].repo_slug == "org/repo"
        assert "feat%2Ftest" in result[0].compare_url

    def test_filters_by_username(self) -> None:
        node = self._make_ref_node(login="otheruser")
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

    def test_excludes_default_branch(self) -> None:
        node = self._make_ref_node(name="main")
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

    def test_excludes_branches_with_open_prs(self) -> None:
        node = self._make_ref_node(open_prs=1)
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

    def test_excludes_old_branches(self) -> None:
        old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        node = self._make_ref_node(committed_date=old_date)
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

    def test_url_encodes_slashes(self) -> None:
        node = self._make_ref_node(name="feature/foo/bar")
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert len(result) == 1
        assert "feature%2Ffoo%2Fbar" in result[0].compare_url

    def test_null_author_skipped(self) -> None:
        node = self._make_ref_node()
        node["target"]["author"]["user"] = None
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

    def test_null_author_object_skipped(self) -> None:
        node = self._make_ref_node()
        node["target"]["author"] = None
        data = self._make_refs_data([node])
        result = parse_refs_results(data, "testuser", "org", "repo", "main")
        assert result == []

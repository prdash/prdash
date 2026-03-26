"""Tests for prdash.models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prdash.models import (
    BranchCommit,
    BranchFileChange,
    CandidateBranch,
    CheckRun,
    MAX_DISPLAY_COMMITS,
    MAX_DISPLAY_FILES,
    PullRequest,
    QueryGroupResult,
    Reviewer,
    TimelineEvent,
    _format_age,
    deduplicate_groups,
    parse_branch_verification,
    parse_compare_response,
    parse_pr_node,
    parse_search_results,
    parse_user_events,
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


# --- is_draft ---


class TestPullRequestIsDraft:
    def test_defaults_to_false(self) -> None:
        pr = _make_pr()
        assert pr.is_draft is False

    def test_can_be_set_true(self) -> None:
        pr = _make_pr(is_draft=True)
        assert pr.is_draft is True


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

    def test_neutral_plus_success_is_passing(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="build", status="COMPLETED", conclusion="SUCCESS"),
                CheckRun(name="lint", status="COMPLETED", conclusion="NEUTRAL"),
            ]
        )
        assert pr.ci_status == "passing"

    def test_skipped_plus_success_is_passing(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="build", status="COMPLETED", conclusion="SUCCESS"),
                CheckRun(name="optional", status="COMPLETED", conclusion="SKIPPED"),
            ]
        )
        assert pr.ci_status == "passing"

    def test_all_neutral_is_passing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="lint", status="COMPLETED", conclusion="NEUTRAL")]
        )
        assert pr.ci_status == "passing"

    def test_all_skipped_is_passing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="opt", status="COMPLETED", conclusion="SKIPPED")]
        )
        assert pr.ci_status == "passing"

    def test_cancelled_is_failing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="COMPLETED", conclusion="CANCELLED")]
        )
        assert pr.ci_status == "failing"

    def test_timed_out_is_failing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="COMPLETED", conclusion="TIMED_OUT")]
        )
        assert pr.ci_status == "failing"

    def test_action_required_is_failing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="COMPLETED", conclusion="ACTION_REQUIRED")]
        )
        assert pr.ci_status == "failing"

    def test_stale_is_failing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="COMPLETED", conclusion="STALE")]
        )
        assert pr.ci_status == "failing"

    def test_startup_failure_is_failing(self) -> None:
        pr = _make_pr(
            checks=[CheckRun(name="build", status="COMPLETED", conclusion="STARTUP_FAILURE")]
        )
        assert pr.ci_status == "failing"

    def test_neutral_plus_in_progress_is_pending(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="lint", status="COMPLETED", conclusion="NEUTRAL"),
                CheckRun(name="build", status="IN_PROGRESS", conclusion=None),
            ]
        )
        assert pr.ci_status == "pending"

    def test_failure_plus_neutral_is_failing(self) -> None:
        pr = _make_pr(
            checks=[
                CheckRun(name="lint", status="COMPLETED", conclusion="NEUTRAL"),
                CheckRun(name="build", status="COMPLETED", conclusion="FAILURE"),
            ]
        )
        assert pr.ci_status == "failing"


# --- Ready to Merge ---


class TestPullRequestReadyToMerge:
    def test_clean_is_ready(self) -> None:
        pr = _make_pr(merge_state_status="CLEAN")
        assert pr.ready_to_merge is True

    def test_blocked_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="BLOCKED")
        assert pr.ready_to_merge is False

    def test_unknown_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="UNKNOWN")
        assert pr.ready_to_merge is False

    def test_behind_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="BEHIND")
        assert pr.ready_to_merge is False

    def test_unstable_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="UNSTABLE")
        assert pr.ready_to_merge is False

    def test_dirty_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="DIRTY")
        assert pr.ready_to_merge is False

    def test_draft_is_not_ready(self) -> None:
        pr = _make_pr(merge_state_status="DRAFT")
        assert pr.ready_to_merge is False

    def test_default_is_not_ready(self) -> None:
        pr = _make_pr()
        assert pr.ready_to_merge is False


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

    def test_is_draft_true(self) -> None:
        pr = parse_pr_node(self._sample_node(isDraft=True))
        assert pr.is_draft is True

    def test_is_draft_false(self) -> None:
        pr = parse_pr_node(self._sample_node(isDraft=False))
        assert pr.is_draft is False

    def test_is_draft_missing_defaults_false(self) -> None:
        node = self._sample_node()
        node.pop("isDraft", None)
        pr = parse_pr_node(node)
        assert pr.is_draft is False

    def test_merge_state_status_parsed(self) -> None:
        pr = parse_pr_node(self._sample_node(mergeStateStatus="CLEAN"))
        assert pr.merge_state_status == "CLEAN"

    def test_merge_state_status_defaults_to_unknown(self) -> None:
        node = self._sample_node()
        node.pop("mergeStateStatus", None)
        pr = parse_pr_node(node)
        assert pr.merge_state_status == "UNKNOWN"

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


# --- parse_user_events ---


class TestParseUserEvents:
    def test_push_event_extraction(self) -> None:
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref": "refs/heads/feat/test"},
            }
        ]
        result = parse_user_events(events, ["org/repo"])
        assert result == {"org/repo": {"feat/test"}}

    def test_create_event_extraction(self) -> None:
        events = [
            {
                "type": "CreateEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref_type": "branch", "ref": "my-branch"},
            }
        ]
        result = parse_user_events(events, ["org/repo"])
        assert result == {"org/repo": {"my-branch"}}

    def test_repo_filtering(self) -> None:
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref": "refs/heads/feat/a"},
            },
            {
                "type": "PushEvent",
                "repo": {"name": "other/repo"},
                "payload": {"ref": "refs/heads/feat/b"},
            },
        ]
        result = parse_user_events(events, ["org/repo"])
        assert "org/repo" in result
        assert "other/repo" not in result

    def test_deduplication(self) -> None:
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref": "refs/heads/feat/a"},
            },
            {
                "type": "PushEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref": "refs/heads/feat/a"},
            },
        ]
        result = parse_user_events(events, ["org/repo"])
        assert result == {"org/repo": {"feat/a"}}

    def test_non_branch_events_ignored(self) -> None:
        events = [
            {
                "type": "WatchEvent",
                "repo": {"name": "org/repo"},
                "payload": {},
            },
            {
                "type": "CreateEvent",
                "repo": {"name": "org/repo"},
                "payload": {"ref_type": "tag", "ref": "v1.0"},
            },
        ]
        result = parse_user_events(events, ["org/repo"])
        assert result == {}

    def test_empty_events(self) -> None:
        result = parse_user_events([], ["org/repo"])
        assert result == {}

    def test_empty_repos_allows_all(self) -> None:
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "any/repo"},
                "payload": {"ref": "refs/heads/feat/x"},
            },
        ]
        result = parse_user_events(events, [])
        assert result == {"any/repo": {"feat/x"}}


# --- parse_branch_verification ---


class TestParseBranchVerification:
    def _make_verification_data(
        self,
        repo_alias: str = "r0",
        branch_alias: str = "b0_0",
        branch_name: str = "feat/test",
        committed_date: str | None = None,
        open_prs: int = 0,
        default_branch: str = "main",
        ref_is_null: bool = False,
    ) -> tuple[dict, list[tuple[str, str, str, str]]]:
        if committed_date is None:
            committed_date = datetime.now(UTC).isoformat()
        alias_map = [(repo_alias, branch_alias, "org/repo", branch_name)]
        ref_data: dict | None = {
            "name": branch_name,
            "target": {"committedDate": committed_date},
            "associatedPullRequests": {"totalCount": open_prs},
        }
        if ref_is_null:
            ref_data = None
        data = {
            "data": {
                repo_alias: {
                    "defaultBranchRef": {"name": default_branch},
                    branch_alias: ref_data,
                }
            }
        }
        return data, alias_map

    def test_basic_success(self) -> None:
        data, alias_map = self._make_verification_data()
        result = parse_branch_verification(data, alias_map)
        assert len(result) == 1
        assert result[0].name == "feat/test"
        assert result[0].repo_slug == "org/repo"
        assert "feat%2Ftest" in result[0].compare_url

    def test_null_ref_skipped(self) -> None:
        data, alias_map = self._make_verification_data(ref_is_null=True)
        result = parse_branch_verification(data, alias_map)
        assert result == []

    def test_open_pr_skipped(self) -> None:
        data, alias_map = self._make_verification_data(open_prs=1)
        result = parse_branch_verification(data, alias_map)
        assert result == []

    def test_old_branch_skipped(self) -> None:
        old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        data, alias_map = self._make_verification_data(committed_date=old_date)
        result = parse_branch_verification(data, alias_map)
        assert result == []

    def test_default_branch_skipped(self) -> None:
        data, alias_map = self._make_verification_data(
            branch_name="main", default_branch="main"
        )
        result = parse_branch_verification(data, alias_map)
        assert result == []

    def test_url_encoding(self) -> None:
        data, alias_map = self._make_verification_data(branch_name="feature/foo/bar")
        result = parse_branch_verification(data, alias_map)
        assert len(result) == 1
        assert "feature%2Ffoo%2Fbar" in result[0].compare_url

    def test_multiple_repos(self) -> None:
        recent = datetime.now(UTC).isoformat()
        alias_map = [
            ("r0", "b0_0", "org/repo1", "feat/a"),
            ("r1", "b1_0", "org/repo2", "feat/b"),
        ]
        data = {
            "data": {
                "r0": {
                    "defaultBranchRef": {"name": "main"},
                    "b0_0": {
                        "name": "feat/a",
                        "target": {"committedDate": recent},
                        "associatedPullRequests": {"totalCount": 0},
                    },
                },
                "r1": {
                    "defaultBranchRef": {"name": "main"},
                    "b1_0": {
                        "name": "feat/b",
                        "target": {"committedDate": recent},
                        "associatedPullRequests": {"totalCount": 0},
                    },
                },
            }
        }
        result = parse_branch_verification(data, alias_map)
        assert len(result) == 2
        names = {b.name for b in result}
        assert names == {"feat/a", "feat/b"}

    def test_default_branch_propagated(self) -> None:
        data, alias_map = self._make_verification_data(default_branch="develop")
        result = parse_branch_verification(data, alias_map)
        assert len(result) == 1
        assert result[0].default_branch == "develop"

    def test_default_branch_defaults_to_main(self) -> None:
        data, alias_map = self._make_verification_data()
        result = parse_branch_verification(data, alias_map)
        assert len(result) == 1
        assert result[0].default_branch == "main"


# --- BranchCommit / BranchFileChange ---


class TestBranchCommit:
    def test_construction(self) -> None:
        c = BranchCommit(
            sha="abc1234567890",
            short_sha="abc1234",
            message="fix: auth",
            authored_date=datetime.now(UTC),
        )
        assert c.sha == "abc1234567890"
        assert c.short_sha == "abc1234"
        assert c.message == "fix: auth"

    def test_frozen(self) -> None:
        c = BranchCommit(
            sha="abc", short_sha="abc", message="x", authored_date=datetime.now(UTC)
        )
        with pytest.raises(Exception):
            c.sha = "new"  # type: ignore[misc]


class TestBranchFileChange:
    def test_construction(self) -> None:
        f = BranchFileChange(
            filename="src/main.py", additions=10, deletions=3, status="modified"
        )
        assert f.filename == "src/main.py"
        assert f.additions == 10
        assert f.deletions == 3
        assert f.status == "modified"


# --- parse_compare_response ---


class TestParseCompareResponse:
    def _make_commit(self, sha: str = "abc1234567890", message: str = "fix: bug") -> dict:
        return {
            "sha": sha,
            "commit": {
                "message": message,
                "author": {"date": "2026-03-10T12:00:00Z"},
            },
        }

    def _make_file(
        self, filename: str = "src/main.py", additions: int = 5, deletions: int = 2, status: str = "modified"
    ) -> dict:
        return {
            "filename": filename,
            "additions": additions,
            "deletions": deletions,
            "status": status,
        }

    def test_happy_path(self) -> None:
        data = {
            "commits": [self._make_commit("aaa1111", "feat: add"), self._make_commit("bbb2222", "fix: typo")],
            "files": [self._make_file("a.py", 10, 3), self._make_file("b.py", 2, 1)],
        }
        result = parse_compare_response(data)
        assert len(result["commits"]) == 2
        assert result["commits"][0].short_sha == "aaa1111"
        assert result["commits"][1].message == "fix: typo"
        assert len(result["files"]) == 2
        assert result["total_commits"] == 2
        assert result["total_files"] == 2
        assert result["total_additions"] == 12
        assert result["total_deletions"] == 4

    def test_caps_commits(self) -> None:
        commits = [self._make_commit(f"sha{i:010d}", f"commit {i}") for i in range(20)]
        data = {"commits": commits, "files": []}
        result = parse_compare_response(data)
        assert len(result["commits"]) == MAX_DISPLAY_COMMITS
        assert result["total_commits"] == 20

    def test_caps_files(self) -> None:
        files = [self._make_file(f"file{i}.py") for i in range(50)]
        data = {"commits": [], "files": files}
        result = parse_compare_response(data)
        assert len(result["files"]) == MAX_DISPLAY_FILES
        assert result["total_files"] == 50

    def test_empty_data(self) -> None:
        result = parse_compare_response({})
        assert result["commits"] == []
        assert result["files"] == []
        assert result["total_commits"] == 0
        assert result["total_files"] == 0
        assert result["total_additions"] == 0
        assert result["total_deletions"] == 0

    def test_totals_sum_all_files(self) -> None:
        """Totals should sum ALL files, not just the capped ones."""
        files = [self._make_file(f"f{i}.py", additions=1, deletions=1) for i in range(50)]
        data = {"commits": [], "files": files}
        result = parse_compare_response(data)
        assert result["total_additions"] == 50
        assert result["total_deletions"] == 50

    def test_multiline_commit_message_takes_first_line(self) -> None:
        data = {
            "commits": [self._make_commit(message="first line\n\nsecond line")],
            "files": [],
        }
        result = parse_compare_response(data)
        assert result["commits"][0].message == "first line"

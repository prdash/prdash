"""Tests for prdash.github (client + queries)."""

from __future__ import annotations

import httpx
import pytest
import respx

from prdash.config import (
    AppConfig,
    QueryGroupConfig,
    QueryGroupType,
)
from prdash.exceptions import AuthError, GitHubAPIError, NetworkError
from prdash.github.client import GitHubClient, create_http_client
from prdash.github.queries import build_search_query


# --- Fixtures ---


def _make_config(**kwargs) -> AppConfig:
    defaults = {
        "repos": ["myorg/myrepo"],
        "username": "testuser",
        "team_slugs": ["team-a", "team-b"],
    }
    defaults.update(kwargs)
    return AppConfig(**defaults)


def _graphql_response(nodes: list[dict], has_next: bool = False, cursor: str | None = None) -> dict:
    return {
        "data": {
            "search": {
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                "nodes": nodes,
            }
        }
    }


def _minimal_pr_node(pr_id: str = "PR_1", number: int = 1, title: str = "Test PR") -> dict:
    return {
        "id": pr_id,
        "number": number,
        "title": title,
        "url": f"https://github.com/org/repo/pull/{number}",
        "createdAt": "2025-01-15T10:00:00Z",
        "body": None,
        "author": {"login": "alice"},
        "labels": {"nodes": []},
        "reviewRequests": {"nodes": []},
        "reviews": {"nodes": []},
        "commits": {"nodes": []},
        "timelineItems": {"nodes": []},
    }


# --- TestBuildSearchQuery ---


def _make_push_event(
    repo: str, branch: str, created_at: str = "2026-03-12T10:00:00Z"
) -> dict:
    return {
        "type": "PushEvent",
        "repo": {"name": repo},
        "payload": {"ref": f"refs/heads/{branch}"},
        "created_at": created_at,
    }


def _events_response(events: list[dict]) -> list[dict]:
    return events


def _branch_verification_response(
    repo_branches: dict[str, list[tuple[str, str, int]]],
    default_branch: str = "main",
) -> dict:
    """Build a GraphQL response for branch verification.

    repo_branches: {repo_alias: [(branch_alias, committed_date, open_pr_count), ...]}
    """
    data: dict[str, dict] = {}
    for repo_alias, branches in repo_branches.items():
        repo_data: dict[str, object] = {"defaultBranchRef": {"name": default_branch}}
        for branch_alias, committed_date, open_prs in branches:
            repo_data[branch_alias] = {
                "name": branch_alias.replace("b", "feat/"),  # placeholder name
                "target": {"committedDate": committed_date},
                "associatedPullRequests": {"totalCount": open_prs},
            }
        data[repo_alias] = repo_data
    return {"data": data}


class TestBuildSearchQuery:
    def test_direct_reviewer(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        queries = build_search_query(config, group)
        assert queries == ["repo:myorg/myrepo is:pr is:open review-requested:testuser"]

    def test_team_reviewer(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        queries = build_search_query(config, group)
        assert len(queries) == 2
        assert "team-review-requested:myorg/team-a" in queries[0]
        assert "team-review-requested:myorg/team-b" in queries[1]

    def test_team_reviewer_no_slugs(self) -> None:
        config = _make_config(team_slugs=[])
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        queries = build_search_query(config, group)
        assert queries == []

    def test_mentioned(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.MENTIONED, name="Mentioned")
        queries = build_search_query(config, group)
        assert queries == ["repo:myorg/myrepo is:pr is:open involves:testuser"]

    def test_authored(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.AUTHORED, name="Authored")
        queries = build_search_query(config, group)
        assert queries == ["repo:myorg/myrepo is:pr is:open author:testuser"]

    def test_assigned(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.ASSIGNED, name="Assigned")
        queries = build_search_query(config, group)
        assert queries == ["repo:myorg/myrepo is:pr is:open assignee:testuser"]

    def test_assigned_no_repos(self) -> None:
        config = _make_config(repos=[])
        group = QueryGroupConfig(type=QueryGroupType.ASSIGNED, name="Assigned")
        queries = build_search_query(config, group)
        assert queries == ["is:pr is:open assignee:testuser"]

    def test_label(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(
            type=QueryGroupType.LABEL, name="Labels", labels=["bug", "urgent"]
        )
        queries = build_search_query(config, group)
        assert len(queries) == 2
        assert 'label:"bug"' in queries[0]
        assert 'label:"urgent"' in queries[1]

    def test_label_no_labels(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.LABEL, name="Labels", labels=[])
        queries = build_search_query(config, group)
        assert queries == []

    # --- Cross-repo tests ---

    def test_no_repos_no_repo_prefix(self) -> None:
        config = _make_config(repos=[])
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        queries = build_search_query(config, group)
        assert len(queries) == 1
        assert "repo:" not in queries[0]
        assert "is:pr is:open review-requested:testuser" in queries[0]

    def test_no_repos_team_reviewer_returns_empty(self) -> None:
        config = _make_config(repos=[])
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        queries = build_search_query(config, group)
        assert queries == []

    def test_multiple_repos_one_query_per_repo(self) -> None:
        config = _make_config(repos=["org/repo1", "org/repo2"])
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        queries = build_search_query(config, group)
        assert len(queries) == 2
        assert "repo:org/repo1" in queries[0]
        assert "repo:org/repo2" in queries[1]

    def test_multiple_repos_team_reviewer_cross_product(self) -> None:
        config = _make_config(repos=["org/repo1", "org/repo2"], team_slugs=["team-a", "team-b"])
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        queries = build_search_query(config, group)
        assert len(queries) == 4  # 2 repos × 2 slugs

    def test_multiple_repos_label_cross_product(self) -> None:
        config = _make_config(repos=["org/repo1", "org/repo2"])
        group = QueryGroupConfig(type=QueryGroupType.LABEL, name="Labels", labels=["bug", "urgent"])
        queries = build_search_query(config, group)
        assert len(queries) == 4  # 2 repos × 2 labels

    def test_ready_to_pr_returns_empty(self) -> None:
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        queries = build_search_query(config, group)
        assert queries == []


# --- TestExecuteQuery ---


class TestExecuteQuery:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={"data": {"viewer": {"login": "test"}}})
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.execute_query("query { viewer { login } }", {})
        assert result["data"]["viewer"]["login"] == "test"

    @pytest.mark.asyncio
    @respx.mock
    async def test_401_raises_auth_error(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            with pytest.raises(AuthError, match="invalid or expired.*gh auth login"):
                await client.execute_query("query { viewer { login } }", {})

    @pytest.mark.asyncio
    @respx.mock
    async def test_403_raises_api_error(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(403, json={"message": "rate limit"})
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            with pytest.raises(GitHubAPIError, match="rate limit"):
                await client.execute_query("query { viewer { login } }", {})

    @pytest.mark.asyncio
    @respx.mock
    async def test_graphql_errors_raise_api_error(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(
                200, json={"errors": [{"message": "Field 'foo' not found"}]}
            )
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            with pytest.raises(GitHubAPIError, match="Field 'foo' not found"):
                await client.execute_query("query { foo }", {})

    @pytest.mark.asyncio
    async def test_network_error(self) -> None:
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            http._transport = _ErrorTransport(httpx.ConnectError("Connection refused"))
            client = GitHubClient(http)
            with pytest.raises(NetworkError, match="Network error"):
                await client.execute_query("query { viewer { login } }", {})

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            http._transport = _ErrorTransport(httpx.ReadTimeout("timed out"))
            client = GitHubClient(http)
            with pytest.raises(NetworkError, match="timed out"):
                await client.execute_query("query { viewer { login } }", {})


class _ErrorTransport(httpx.AsyncBaseTransport):
    """Transport that always raises a given exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise self._exc


# --- TestFetchGroup ---


class TestFetchGroup:
    @pytest.mark.asyncio
    @respx.mock
    async def test_direct_reviewer(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(
                200, json=_graphql_response([_minimal_pr_node()])
            )
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert result.group_name == "Direct"
        assert len(result.pull_requests) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_team_reviewer_merges_and_deduplicates(self) -> None:
        """Multiple team queries should merge results and deduplicate by ID."""
        respx.post("https://api.github.com/graphql").mock(
            side_effect=[
                httpx.Response(200, json=_graphql_response([_minimal_pr_node("PR_1", 1)])),
                httpx.Response(200, json=_graphql_response([_minimal_pr_node("PR_1", 1), _minimal_pr_node("PR_2", 2)])),
            ]
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert len(result.pull_requests) == 2  # PR_1 deduplicated

    @pytest.mark.asyncio
    @respx.mock
    async def test_label_merges(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            side_effect=[
                httpx.Response(200, json=_graphql_response([_minimal_pr_node("PR_1", 1)])),
                httpx.Response(200, json=_graphql_response([_minimal_pr_node("PR_2", 2)])),
            ]
        )
        config = _make_config()
        group = QueryGroupConfig(
            type=QueryGroupType.LABEL, name="Labels", labels=["bug", "urgent"]
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert len(result.pull_requests) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_slugs_returns_no_prs(self) -> None:
        config = _make_config(team_slugs=[])
        group = QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert result.pull_requests == []


# --- TestFetchAllGroups ---


class TestFetchAllGroups:
    @pytest.mark.asyncio
    @respx.mock
    async def test_parallel_fetch(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(
                200, json=_graphql_response([_minimal_pr_node()])
            )
        )
        config = _make_config(
            query_groups=[
                QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct"),
                QueryGroupConfig(type=QueryGroupType.AUTHORED, name="Authored"),
            ]
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            results, errors = await client.fetch_all_groups(config)
        assert len(results) == 2
        assert len(errors) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_failed_group_returns_error_tuple(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            side_effect=[
                httpx.Response(200, json=_graphql_response([_minimal_pr_node()])),
                httpx.Response(500),
            ]
        )
        config = _make_config(
            query_groups=[
                QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct"),
                QueryGroupConfig(type=QueryGroupType.AUTHORED, name="Authored"),
            ]
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            results, errors = await client.fetch_all_groups(config)
        assert len(results) == 1
        assert results[0].group_name == "Direct"
        assert len(errors) == 1
        assert errors[0][0] == "Authored"
        assert isinstance(errors[0][1], Exception)

    @pytest.mark.asyncio
    @respx.mock
    async def test_only_enabled_groups(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(
                200, json=_graphql_response([_minimal_pr_node()])
            )
        )
        config = _make_config(
            query_groups=[
                QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct"),
                QueryGroupConfig(
                    type=QueryGroupType.AUTHORED, name="Authored", enabled=False
                ),
            ]
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            results, errors = await client.fetch_all_groups(config)
        assert len(results) == 1
        assert results[0].group_name == "Direct"
        assert len(errors) == 0


# --- TestPagination ---


class TestPagination:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_page(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(
                200, json=_graphql_response([_minimal_pr_node()])
            )
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert len(result.pull_requests) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_multiple_pages(self) -> None:
        respx.post("https://api.github.com/graphql").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_graphql_response(
                        [_minimal_pr_node("PR_1", 1)], has_next=True, cursor="c1"
                    ),
                ),
                httpx.Response(
                    200,
                    json=_graphql_response([_minimal_pr_node("PR_2", 2)]),
                ),
            ]
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_group(config, group)
        assert len(result.pull_requests) == 2


# --- TestCreateHttpClient ---


# --- TestFetchCandidateBranches ---


class TestFetchCandidateBranches:
    @pytest.mark.asyncio
    @respx.mock
    async def test_single_repo(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        # Mock REST events endpoint
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/test"),
                ])),
                httpx.Response(200, json=[]),  # page 2 empty
            ]
        )
        # Mock GraphQL verification
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "r0": {
                        "defaultBranchRef": {"name": "main"},
                        "b0_0": {
                            "name": "feat/test",
                            "target": {"committedDate": recent},
                            "associatedPullRequests": {"totalCount": 0},
                        },
                    }
                }
            })
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert result.group_name == "Ready to PR"
        assert len(result.branches) == 1
        assert result.branches[0].name == "feat/test"

    @pytest.mark.asyncio
    @respx.mock
    async def test_multi_repo(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("org/repo1", "feat/a"),
                    _make_push_event("org/repo2", "feat/b"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
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
            })
        )
        config = _make_config(repos=["org/repo1", "org/repo2"])
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert len(result.branches) == 2

    @pytest.mark.asyncio
    async def test_empty_repos(self) -> None:
        config = _make_config(repos=[])
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert result.branches == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_events(self) -> None:
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            return_value=httpx.Response(200, json=[])
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert result.branches == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_deleted_branch(self) -> None:
        """Branch in events but null ref in GraphQL (deleted)."""
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/deleted"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "r0": {
                        "defaultBranchRef": {"name": "main"},
                        "b0_0": None,  # deleted
                    }
                }
            })
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert result.branches == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_branch_with_open_pr(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/has-pr"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "r0": {
                        "defaultBranchRef": {"name": "main"},
                        "b0_0": {
                            "name": "feat/has-pr",
                            "target": {"committedDate": recent},
                            "associatedPullRequests": {"totalCount": 1},
                        },
                    }
                }
            })
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert result.branches == []


# --- TestFetchAllGroupsWithBranches ---


class TestFetchAllGroupsWithBranches:
    @pytest.mark.asyncio
    @respx.mock
    async def test_dispatches_ready_to_pr(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        # Mock REST events
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/test"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        # Mock GraphQL: first call for PR search, second for branch verification
        respx.post("https://api.github.com/graphql").mock(
            side_effect=[
                httpx.Response(200, json=_graphql_response([_minimal_pr_node()])),
                httpx.Response(200, json={
                    "data": {
                        "r0": {
                            "defaultBranchRef": {"name": "main"},
                            "b0_0": {
                                "name": "feat/test",
                                "target": {"committedDate": recent},
                                "associatedPullRequests": {"totalCount": 0},
                            },
                        }
                    }
                }),
            ]
        )
        config = _make_config(
            query_groups=[
                QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Direct"),
                QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR"),
            ]
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            results, errors = await client.fetch_all_groups(config)
        assert len(results) == 2
        assert len(errors) == 0
        pr_group = next(r for r in results if r.group_name == "Direct")
        branch_group = next(r for r in results if r.group_name == "Ready to PR")
        assert len(pr_group.pull_requests) == 1
        assert len(branch_group.branches) == 1


# --- TestFetchBranchCompare ---


class TestFetchBranchCompare:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self) -> None:
        from datetime import UTC, datetime
        respx.get(url__regex=r".*/repos/.*/compare/.*").mock(
            return_value=httpx.Response(200, json={
                "commits": [
                    {
                        "sha": "abc1234567890",
                        "commit": {
                            "message": "feat: add widget",
                            "author": {"date": "2026-03-10T12:00:00Z"},
                        },
                    }
                ],
                "files": [
                    {
                        "filename": "src/widget.py",
                        "additions": 50,
                        "deletions": 3,
                        "status": "added",
                    }
                ],
            })
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client._fetch_branch_compare("org/repo", "main", "feat/widget")
        assert result is not None
        assert len(result["commits"]) == 1
        assert result["commits"][0].short_sha == "abc1234"
        assert len(result["files"]) == 1
        assert result["total_additions"] == 50

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_returns_none(self) -> None:
        respx.get(url__regex=r".*/repos/.*/compare/.*").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client._fetch_branch_compare("org/repo", "main", "gone-branch")
        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self) -> None:
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            http._transport = _ErrorTransport(httpx.ConnectError("Connection refused"))
            client = GitHubClient(http)
            result = await client._fetch_branch_compare("org/repo", "main", "feat/x")
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_encodes_branch_name(self) -> None:
        route = respx.get(url__regex=r".*/repos/.*/compare/.*").mock(
            return_value=httpx.Response(200, json={"commits": [], "files": []})
        )
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            await client._fetch_branch_compare("org/repo", "main", "feat/my branch")
        assert route.called
        url = str(route.calls[0].request.url)
        assert "feat%2Fmy%20branch" in url


# --- TestFetchCandidateBranchesEnrichment ---


class TestFetchCandidateBranchesEnrichment:
    @pytest.mark.asyncio
    @respx.mock
    async def test_enriches_with_compare_data(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        # Mock REST events
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/test"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        # Mock GraphQL verification
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "r0": {
                        "defaultBranchRef": {"name": "main"},
                        "b0_0": {
                            "name": "feat/test",
                            "target": {"committedDate": recent},
                            "associatedPullRequests": {"totalCount": 0},
                        },
                    }
                }
            })
        )
        # Mock compare API
        respx.get(url__regex=r".*/repos/.*/compare/.*").mock(
            return_value=httpx.Response(200, json={
                "commits": [
                    {
                        "sha": "abc1234567890",
                        "commit": {
                            "message": "feat: stuff",
                            "author": {"date": recent},
                        },
                    }
                ],
                "files": [
                    {"filename": "src/a.py", "additions": 10, "deletions": 2, "status": "modified"},
                ],
            })
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert len(result.branches) == 1
        branch = result.branches[0]
        assert len(branch.commits) == 1
        assert branch.commits[0].short_sha == "abc1234"
        assert len(branch.files) == 1
        assert branch.total_additions == 10
        assert branch.total_deletions == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_failure_returns_branch_unchanged(self) -> None:
        from datetime import UTC, datetime
        recent = datetime.now(UTC).isoformat()
        respx.get(url__regex=r".*/users/.*/events.*").mock(
            side_effect=[
                httpx.Response(200, json=_events_response([
                    _make_push_event("myorg/myrepo", "feat/test"),
                ])),
                httpx.Response(200, json=[]),
            ]
        )
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "r0": {
                        "defaultBranchRef": {"name": "main"},
                        "b0_0": {
                            "name": "feat/test",
                            "target": {"committedDate": recent},
                            "associatedPullRequests": {"totalCount": 0},
                        },
                    }
                }
            })
        )
        # Compare API fails
        respx.get(url__regex=r".*/repos/.*/compare/.*").mock(
            return_value=httpx.Response(500)
        )
        config = _make_config()
        group = QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR")
        async with httpx.AsyncClient(base_url="https://api.github.com") as http:
            client = GitHubClient(http)
            result = await client.fetch_candidate_branches(config, group)
        assert len(result.branches) == 1
        # Branch still has empty defaults
        assert result.branches[0].commits == []
        assert result.branches[0].files == []


class TestCreateHttpClient:
    def test_creates_client_with_auth(self) -> None:
        client = create_http_client("ghp_test123")
        assert client.headers["authorization"] == "Bearer ghp_test123"
        assert str(client.base_url) == "https://api.github.com"

    def test_default_timeout(self) -> None:
        client = create_http_client("ghp_test123")
        assert client.timeout.connect == 30.0

    def test_custom_timeout(self) -> None:
        client = create_http_client("ghp_test123", timeout=60.0)
        assert client.timeout.connect == 60.0

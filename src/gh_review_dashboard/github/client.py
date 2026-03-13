"""Async GitHub GraphQL client."""

from __future__ import annotations

import asyncio

import httpx

from gh_review_dashboard.config import AppConfig, QueryGroupConfig, QueryGroupType
from gh_review_dashboard.exceptions import AuthError, GitHubAPIError, NetworkError
from gh_review_dashboard.github.queries import (
    BRANCH_REFS_QUERY,
    DEFAULT_PAGE_SIZE,
    PR_SEARCH_QUERY,
    build_search_query,
)
from gh_review_dashboard.models import (
    CandidateBranch,
    PullRequest,
    QueryGroupResult,
    parse_refs_results,
    parse_search_results,
)


class GitHubClient:
    """Async client for GitHub's GraphQL API."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def execute_query(
        self, query: str, variables: dict[str, object]
    ) -> dict[str, object]:
        """Execute a GraphQL query and return the response data."""
        try:
            response = await self._client.post(
                "/graphql", json={"query": query, "variables": variables}
            )
        except httpx.TimeoutException as e:
            raise NetworkError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {e}") from e

        if response.status_code == 401:
            raise AuthError(
                "GitHub token is invalid or expired. "
                "Run 'gh auth login' to re-authenticate."
            )
        if response.status_code == 403:
            raise GitHubAPIError("GitHub API rate limit exceeded or insufficient permissions")

        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            messages = [e.get("message", str(e)) for e in data["errors"]]
            raise GitHubAPIError(f"GraphQL errors: {'; '.join(messages)}")

        return data

    async def _fetch_search_pages(self, search_query: str) -> list[PullRequest]:
        """Fetch all pages for a single search query."""
        all_prs: list[PullRequest] = []
        cursor: str | None = None
        has_next = True

        while has_next:
            variables: dict[str, object] = {
                "searchQuery": search_query,
                "first": DEFAULT_PAGE_SIZE,
                "after": cursor,
            }
            data = await self.execute_query(PR_SEARCH_QUERY, variables)
            prs, has_next, cursor = parse_search_results(data)  # type: ignore[arg-type]
            all_prs.extend(prs)

        return all_prs

    async def fetch_group(
        self, config: AppConfig, group: QueryGroupConfig
    ) -> QueryGroupResult:
        """Fetch PRs for a single query group, merging results from multiple queries."""
        search_queries = build_search_query(config, group)
        if not search_queries:
            return QueryGroupResult(
                group_name=group.name,
                group_type=group.type.value,
                pull_requests=[],
            )
        all_prs: list[PullRequest] = []
        seen_ids: set[str] = set()

        for sq in search_queries:
            prs = await self._fetch_search_pages(sq)
            for pr in prs:
                if pr.id not in seen_ids:
                    seen_ids.add(pr.id)
                    all_prs.append(pr)

        return QueryGroupResult(
            group_name=group.name,
            group_type=group.type.value,
            pull_requests=all_prs,
        )

    async def fetch_candidate_branches(
        self, config: AppConfig, group: QueryGroupConfig
    ) -> QueryGroupResult:
        """Fetch candidate branches (no open PR) for the user across configured repos."""
        if not config.repos:
            return QueryGroupResult(
                group_name=group.name,
                group_type=group.type.value,
            )

        all_branches: list[CandidateBranch] = []
        for repo_slug in config.repos:
            owner, name = repo_slug.split("/", 1)
            data = await self.execute_query(
                BRANCH_REFS_QUERY, {"owner": owner, "name": name}
            )
            repository = data.get("data", {}).get("repository", {})  # type: ignore[union-attr]
            default_ref = repository.get("defaultBranchRef") or {}
            default_branch = default_ref.get("name", "main")
            branches = parse_refs_results(
                data, config.username, owner, name, default_branch  # type: ignore[arg-type]
            )
            all_branches.extend(branches)

        return QueryGroupResult(
            group_name=group.name,
            group_type=group.type.value,
            branches=all_branches,
        )

    async def _fetch_for_group(
        self, config: AppConfig, group: QueryGroupConfig
    ) -> QueryGroupResult:
        """Dispatch to the appropriate fetch method based on group type."""
        if group.type == QueryGroupType.READY_TO_PR:
            return await self.fetch_candidate_branches(config, group)
        return await self.fetch_group(config, group)

    async def fetch_all_groups(
        self, config: AppConfig
    ) -> tuple[list[QueryGroupResult], list[tuple[str, Exception]]]:
        """Fetch PRs for all enabled query groups in parallel.

        Returns:
            A tuple of (successful results, list of (group_name, exception) for failures).
        """
        enabled_groups = [g for g in config.query_groups if g.enabled]

        results = await asyncio.gather(
            *(self._fetch_for_group(config, g) for g in enabled_groups),
            return_exceptions=True,
        )

        group_results: list[QueryGroupResult] = []
        errors: list[tuple[str, Exception]] = []
        for group, result in zip(enabled_groups, results):
            if isinstance(result, Exception):
                errors.append((group.name, result))
            else:
                group_results.append(result)

        return group_results, errors

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def create_http_client(token: str, timeout: float = 30.0) -> httpx.AsyncClient:
    """Create a configured httpx AsyncClient for the GitHub API."""
    return httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=httpx.Timeout(timeout),
    )

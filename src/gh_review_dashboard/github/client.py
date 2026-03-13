"""Async GitHub GraphQL client."""

from __future__ import annotations

import asyncio
import urllib.parse

import httpx

from gh_review_dashboard.config import AppConfig, QueryGroupConfig, QueryGroupType
from gh_review_dashboard.exceptions import AuthError, GitHubAPIError, NetworkError
from gh_review_dashboard.github.queries import (
    DEFAULT_PAGE_SIZE,
    PR_SEARCH_QUERY,
    build_branch_verification_query,
    build_search_query,
)
from gh_review_dashboard.models import (
    CandidateBranch,
    PullRequest,
    QueryGroupResult,
    parse_branch_verification,
    parse_compare_response,
    parse_search_results,
    parse_user_events,
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

    async def _fetch_user_events(self, username: str) -> list[dict]:
        """Fetch recent user events from the REST API (up to 3 pages)."""
        all_events: list[dict] = []
        for page in range(1, 4):
            url = f"/users/{username}/events?per_page=100&page={page}"
            try:
                response = await self._client.get(url)
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
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded or insufficient permissions"
                )
            response.raise_for_status()

            events = response.json()
            if not events:
                break
            all_events.extend(events)

            # Stop early if oldest event on this page is older than 7 days
            from datetime import UTC, datetime, timedelta

            oldest_str = events[-1].get("created_at", "")
            if oldest_str:
                oldest = datetime.fromisoformat(oldest_str.replace("Z", "+00:00"))
                if oldest < datetime.now(UTC) - timedelta(days=7):
                    break

        return all_events

    async def _fetch_branch_compare(
        self,
        repo_slug: str,
        default_branch: str,
        branch_name: str,
    ) -> dict | None:
        """Fetch compare data for a branch vs its default branch.

        Returns parsed compare fields or None on any error.
        """
        encoded_branch = urllib.parse.quote(branch_name, safe="")
        url = f"/repos/{repo_slug}/compare/{default_branch}...{encoded_branch}"
        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return None
            return parse_compare_response(response.json())
        except Exception:
            return None

    async def fetch_candidate_branches(
        self, config: AppConfig, group: QueryGroupConfig
    ) -> QueryGroupResult:
        """Fetch candidate branches (no open PR) for the user across configured repos."""
        if not config.repos:
            return QueryGroupResult(
                group_name=group.name,
                group_type=group.type.value,
            )

        # Phase 1: Discover branches from user events
        events = await self._fetch_user_events(config.username)
        repo_branches = parse_user_events(events, config.repos)

        if not repo_branches:
            return QueryGroupResult(
                group_name=group.name,
                group_type=group.type.value,
            )

        # Phase 2: Verify branches via batched GraphQL
        query, variables, alias_map = build_branch_verification_query(repo_branches)
        data = await self.execute_query(query, variables)
        branches = parse_branch_verification(data, alias_map)  # type: ignore[arg-type]

        # Phase 3: Enrich verified branches with compare data
        if branches:
            compare_results = await asyncio.gather(
                *(
                    self._fetch_branch_compare(
                        b.repo_slug, b.default_branch, b.name
                    )
                    for b in branches
                ),
                return_exceptions=True,
            )
            enriched: list[CandidateBranch] = []
            for branch, result in zip(branches, compare_results):
                if isinstance(result, dict):
                    enriched.append(branch.model_copy(update=result))
                else:
                    enriched.append(branch)
            branches = enriched

        return QueryGroupResult(
            group_name=group.name,
            group_type=group.type.value,
            branches=branches,
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

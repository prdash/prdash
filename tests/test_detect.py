"""Tests for auto-detection helpers."""

from __future__ import annotations

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_review_dashboard.detect import (
    detect_repo_from_git_remote,
    detect_team_slugs,
    detect_username,
)


class TestDetectRepoFromGitRemote:
    def test_ssh_url(self) -> None:
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="git@github.com:my-org/my-repo.git\n"
        )
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() == ("my-org", "my-repo")

    def test_ssh_url_no_dot_git(self) -> None:
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="git@github.com:my-org/my-repo\n"
        )
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() == ("my-org", "my-repo")

    def test_https_url(self) -> None:
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/acme/widget.git\n"
        )
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() == ("acme", "widget")

    def test_https_url_no_dot_git(self) -> None:
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/acme/widget\n"
        )
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() == ("acme", "widget")

    def test_git_not_found(self) -> None:
        with patch(
            "gh_review_dashboard.detect.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert detect_repo_from_git_remote() is None

    def test_no_origin_remote(self) -> None:
        with patch(
            "gh_review_dashboard.detect.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert detect_repo_from_git_remote() is None

    def test_empty_output(self) -> None:
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout="\n")
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() is None

    def test_non_github_url(self) -> None:
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="git@gitlab.com:org/repo.git\n"
        )
        with patch("gh_review_dashboard.detect.subprocess.run", return_value=result):
            assert detect_repo_from_git_remote() is None


class TestDetectUsername:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        with patch(
            "gh_review_dashboard.detect.validate_token",
            new_callable=AsyncMock,
            return_value="octocat",
        ):
            assert await detect_username("ghp_test") == "octocat"

    @pytest.mark.asyncio
    async def test_failure_returns_none(self) -> None:
        with patch(
            "gh_review_dashboard.detect.validate_token",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            assert await detect_username("ghp_bad") is None


def _mock_team_client(teams_json: list) -> AsyncMock:
    """Create a mock httpx.AsyncClient that returns given teams JSON."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = teams_json

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestDetectTeamSlugs:
    @pytest.mark.asyncio
    async def test_filters_by_org(self) -> None:
        mock_client = _mock_team_client([
            {"slug": "backend", "organization": {"login": "my-org"}},
            {"slug": "frontend", "organization": {"login": "my-org"}},
            {"slug": "other-team", "organization": {"login": "other-org"}},
        ])
        with patch("gh_review_dashboard.detect.httpx.AsyncClient", return_value=mock_client):
            result = await detect_team_slugs("ghp_test", "my-org", "user")
        assert result == ["backend", "frontend"]

    @pytest.mark.asyncio
    async def test_case_insensitive_org_match(self) -> None:
        mock_client = _mock_team_client([
            {"slug": "team-a", "organization": {"login": "My-Org"}},
        ])
        with patch("gh_review_dashboard.detect.httpx.AsyncClient", return_value=mock_client):
            result = await detect_team_slugs("ghp_test", "my-org", "user")
        assert result == ["team-a"]

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("gh_review_dashboard.detect.httpx.AsyncClient", return_value=mock_client):
            result = await detect_team_slugs("ghp_test", "my-org", "user")
        assert result == []

    @pytest.mark.asyncio
    async def test_no_teams_returns_empty(self) -> None:
        mock_client = _mock_team_client([])
        with patch("gh_review_dashboard.detect.httpx.AsyncClient", return_value=mock_client):
            result = await detect_team_slugs("ghp_test", "my-org", "user")
        assert result == []

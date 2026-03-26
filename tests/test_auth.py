"""Tests for prdash.auth."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import httpx
import pytest
import respx

from prdash.auth import get_github_token, validate_token
from prdash.exceptions import AuthError


# --- get_github_token tests ---


def test_get_token_success() -> None:
    result = subprocess.CompletedProcess(
        args=["gh", "auth", "token"],
        returncode=0,
        stdout="ghp_abc123token\n",
        stderr="",
    )
    with patch("prdash.auth.subprocess.run", return_value=result):
        assert get_github_token() == "ghp_abc123token"


def test_get_token_gh_not_installed() -> None:
    with patch(
        "prdash.auth.subprocess.run", side_effect=FileNotFoundError
    ):
        with pytest.raises(AuthError, match="not found"):
            get_github_token()


def test_get_token_not_authenticated() -> None:
    with patch(
        "prdash.auth.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "gh"),
    ):
        with pytest.raises(AuthError, match="Not authenticated"):
            get_github_token()


def test_get_token_empty_result() -> None:
    result = subprocess.CompletedProcess(
        args=["gh", "auth", "token"],
        returncode=0,
        stdout="  \n",
        stderr="",
    )
    with patch("prdash.auth.subprocess.run", return_value=result):
        with pytest.raises(AuthError, match="empty result"):
            get_github_token()


# --- validate_token tests ---


@pytest.mark.asyncio
@respx.mock
async def test_validate_token_success() -> None:
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "octocat"})
    )
    username = await validate_token("ghp_valid")
    assert username == "octocat"


@pytest.mark.asyncio
@respx.mock
async def test_validate_token_invalid() -> None:
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    with pytest.raises(AuthError, match="invalid or expired"):
        await validate_token("ghp_bad")


@pytest.mark.asyncio
@respx.mock
async def test_validate_token_other_http_error() -> None:
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(AuthError, match="GitHub API error"):
        await validate_token("ghp_valid")

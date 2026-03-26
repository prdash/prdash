"""GitHub authentication via the gh CLI."""

from __future__ import annotations

import subprocess

import httpx

from prdash.exceptions import AuthError


def get_github_token() -> str:
    """Extract GitHub token from the gh CLI.

    Raises:
        AuthError: If gh is not installed, not authenticated, or returns empty.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise AuthError(
            "GitHub CLI (gh) not found. Install it from https://cli.github.com/"
        )
    except subprocess.CalledProcessError:
        raise AuthError(
            "Not authenticated with GitHub CLI. Run 'gh auth login' first."
        )

    token = result.stdout.strip()
    if not token:
        raise AuthError(
            "gh auth token returned empty result. Run 'gh auth login' first."
        )
    return token


async def validate_token(token: str) -> str:
    """Validate a GitHub token by calling GET /user.

    Returns the authenticated username.

    Raises:
        AuthError: If the token is invalid, expired, or the request fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
    if response.status_code == 401:
        raise AuthError(
            "GitHub token is invalid or expired. Run 'gh auth login' to re-authenticate."
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AuthError(f"GitHub API error: {exc}") from exc
    return response.json()["login"]

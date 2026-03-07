"""Auto-detection helpers for first-run setup wizard."""

from __future__ import annotations

import re
import subprocess

import httpx

from gh_review_dashboard.auth import validate_token


def detect_repo_from_git_remote() -> tuple[str, str] | None:
    """Parse org and repo name from git remote -v origin.

    Supports SSH (git@github.com:org/repo.git) and HTTPS
    (https://github.com/org/repo.git) formats.

    Returns (org, repo_name) or None on failure.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    url = result.stdout.strip()
    if not url:
        return None

    # SSH: git@github.com:org/repo.git
    ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS: https://github.com/org/repo.git
    https_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", url
    )
    if https_match:
        return https_match.group(1), https_match.group(2)

    return None


async def detect_username(token: str) -> str | None:
    """Detect GitHub username by validating the token.

    Returns the username or None on any failure.
    """
    try:
        return await validate_token(token)
    except Exception:
        return None


async def detect_team_slugs(
    token: str, org: str, username: str
) -> list[str]:
    """Fetch team slugs for the user within the given org.

    Returns a list of team slugs, or empty list on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/teams",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"per_page": 100},
            )
            response.raise_for_status()
            teams = response.json()
    except Exception:
        return []

    return [
        team["slug"]
        for team in teams
        if team.get("organization", {}).get("login", "").lower() == org.lower()
    ]

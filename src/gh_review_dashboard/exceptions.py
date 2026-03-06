"""Shared exception hierarchy for the dashboard."""


class DashboardError(Exception):
    """Base exception for all dashboard errors."""


class AuthError(DashboardError):
    """GitHub authentication failed (gh CLI missing, token expired)."""


class ConfigError(DashboardError):
    """Configuration loading or validation failed."""


class GitHubAPIError(DashboardError):
    """GitHub API request failed (network, rate limit, query error)."""

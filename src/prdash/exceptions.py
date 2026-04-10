"""Shared exception hierarchy for the dashboard."""


class DashboardError(Exception):
    """Base exception for all dashboard errors."""


class AuthError(DashboardError):
    """GitHub authentication failed (gh CLI missing, token expired)."""


class ConfigError(DashboardError):
    """Configuration loading or validation failed."""


class GitHubAPIError(DashboardError):
    """GitHub API request failed (rate limit, query error)."""


class NetworkError(DashboardError):
    """Network or timeout error communicating with GitHub."""


class ClipboardError(DashboardError):
    """Clipboard operation failed (pbcopy missing or failed)."""

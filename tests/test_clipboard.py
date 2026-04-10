"""Tests for clipboard utilities."""

from prdash.exceptions import ClipboardError, DashboardError


def test_clipboard_error_is_dashboard_error():
    assert issubclass(ClipboardError, DashboardError)

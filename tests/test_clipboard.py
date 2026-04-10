"""Tests for clipboard utilities."""

from unittest.mock import AsyncMock, patch

import pytest

from prdash.exceptions import ClipboardError, DashboardError


def test_clipboard_error_is_dashboard_error():
    assert issubclass(ClipboardError, DashboardError)


from prdash.clipboard import copy_to_clipboard


@pytest.mark.asyncio
async def test_copy_to_clipboard_calls_pbcopy():
    """Happy path: text is piped to pbcopy via stdin."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0

    with patch("prdash.clipboard.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await copy_to_clipboard("https://github.com/org/repo/pull/42")

    mock_exec.assert_called_once_with(
        "pbcopy",
        stdin=-1,  # asyncio.subprocess.PIPE
    )
    mock_proc.communicate.assert_called_once_with(
        input=b"https://github.com/org/repo/pull/42",
    )


@pytest.mark.asyncio
async def test_copy_to_clipboard_raises_on_missing_pbcopy():
    """FileNotFoundError from subprocess raises ClipboardError."""
    with patch(
        "prdash.clipboard.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("pbcopy not found"),
    ):
        with pytest.raises(ClipboardError, match="pbcopy not found"):
            await copy_to_clipboard("text")


@pytest.mark.asyncio
async def test_copy_to_clipboard_raises_on_nonzero_exit():
    """Non-zero return code raises ClipboardError."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"some error"))
    mock_proc.returncode = 1

    with patch("prdash.clipboard.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(ClipboardError, match="some error"):
            await copy_to_clipboard("text")

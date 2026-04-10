"""System clipboard utilities (macOS pbcopy)."""

from __future__ import annotations

import asyncio

from prdash.exceptions import ClipboardError


async def copy_to_clipboard(text: str) -> None:
    """Copy *text* to the system clipboard via pbcopy."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pbcopy",
            stdin=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate(input=text.encode("utf-8"))
    except FileNotFoundError as exc:
        raise ClipboardError("pbcopy not found — clipboard requires macOS") from exc

    if proc.returncode != 0:
        err = stderr.decode().strip() if stderr else "unknown error"
        raise ClipboardError(f"pbcopy failed: {err}")

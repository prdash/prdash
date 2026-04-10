# T52 — Copy PR URL/Number to Clipboard — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `y`/`Y` keybindings to copy PR URL or short reference to the system clipboard from the TUI.

**Architecture:** New `clipboard.py` module handles subprocess calls to `pbcopy`. Keybindings and action methods live in `NavigableListView` (same pattern as the existing `c` checkout action). Both PR items and "Ready to PR" branch items are supported.

**Tech Stack:** Python asyncio subprocess, pbcopy (macOS), Textual keybindings, pytest with AsyncMock

**Spec:** `docs/superpowers/specs/2026-04-10-t52-clipboard-copy-design.md`

---

### Task 1: Add `ClipboardError` exception

**Files:**
- Modify: `src/prdash/exceptions.py:20` (append after `NetworkError`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_clipboard.py`:

```python
"""Tests for clipboard utilities."""

from prdash.exceptions import ClipboardError, DashboardError


def test_clipboard_error_is_dashboard_error():
    assert issubclass(ClipboardError, DashboardError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_clipboard.py::test_clipboard_error_is_dashboard_error -v`
Expected: FAIL — `ImportError: cannot import name 'ClipboardError'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/prdash/exceptions.py` after `NetworkError`:

```python
class ClipboardError(DashboardError):
    """Clipboard operation failed (pbcopy missing or failed)."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_clipboard.py::test_clipboard_error_is_dashboard_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prdash/exceptions.py tests/test_clipboard.py
git commit -m "feat(clipboard): add ClipboardError exception"
```

---

### Task 2: Implement `copy_to_clipboard()` with tests

**Files:**
- Create: `src/prdash/clipboard.py`
- Modify: `tests/test_clipboard.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_clipboard.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_clipboard.py -v`
Expected: 3 FAIL — `ModuleNotFoundError: No module named 'prdash.clipboard'`

- [ ] **Step 3: Write minimal implementation**

Create `src/prdash/clipboard.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_clipboard.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/prdash/clipboard.py tests/test_clipboard.py
git commit -m "feat(clipboard): add copy_to_clipboard async utility"
```

---

### Task 3: Add `y`/`Y` keybindings and action methods

**Files:**
- Modify: `src/prdash/widgets/pr_list.py:187-191` (BINDINGS) and add action methods after `action_checkout` (~line 231)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pr_list.py`:

```python
# --- Clipboard copy tests (T52) ---


@pytest.mark.asyncio
async def test_copy_url_copies_pr_url(sample_pr):
    """y key copies the selected PR's full URL to clipboard."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Review Requested",
                group_type="review_requested",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move down to the first PR row (index 0 is group header)
        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.copy_to_clipboard", new_callable=AsyncMock) as mock_copy:
            await pilot.press("y")
            await pilot.pause()
            mock_copy.assert_called_once_with(sample_pr.url)


@pytest.mark.asyncio
async def test_copy_ref_copies_pr_reference(sample_pr):
    """Y key copies org/repo#number reference."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Review Requested",
                group_type="review_requested",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.copy_to_clipboard", new_callable=AsyncMock) as mock_copy:
            await pilot.press("Y")
            await pilot.pause()
            expected = f"{sample_pr.repo_slug}#{sample_pr.number}"
            mock_copy.assert_called_once_with(expected)


@pytest.mark.asyncio
async def test_copy_url_copies_branch_compare_url():
    """y key on a BranchRow copies the compare URL."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.copy_to_clipboard", new_callable=AsyncMock) as mock_copy:
            await pilot.press("y")
            await pilot.pause()
            mock_copy.assert_called_once_with(branch.compare_url)


@pytest.mark.asyncio
async def test_copy_ref_copies_branch_name():
    """Y key on a BranchRow copies the branch name."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.copy_to_clipboard", new_callable=AsyncMock) as mock_copy:
            await pilot.press("Y")
            await pilot.pause()
            mock_copy.assert_called_once_with(branch.name)


@pytest.mark.asyncio
async def test_copy_url_noop_on_group_header(sample_groups):
    """y key on a group header does nothing."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Don't press j — stay on the group header
        with patch("prdash.widgets.pr_list.copy_to_clipboard", new_callable=AsyncMock) as mock_copy:
            await pilot.press("y")
            await pilot.pause()
            mock_copy.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pr_list.py -k "copy_url or copy_ref" -v`
Expected: FAIL — no `copy_to_clipboard` to patch / no action bound

- [ ] **Step 3: Write implementation**

In `src/prdash/widgets/pr_list.py`:

1. Add import at top:
```python
from prdash.clipboard import copy_to_clipboard
```

2. Add bindings to `NavigableListView.BINDINGS` (after the `c` checkout binding):
```python
Binding("y", "copy_url", "Copy URL", show=False),
Binding("Y", "copy_ref", "Copy Ref", show=False),
```

3. Add action methods after `action_checkout`:
```python
async def action_copy_url(self) -> None:
    """Copy the selected PR URL or branch compare URL to clipboard."""
    item = self.highlighted_child
    if isinstance(item, PRRow):
        value = item.pr.url
    elif isinstance(item, BranchRow):
        value = item.branch.compare_url
    else:
        return
    try:
        await copy_to_clipboard(value)
        self.app.notify(f"Copied: {value}", severity="information")
    except ClipboardError as exc:
        self.app.notify(str(exc), severity="error")

async def action_copy_ref(self) -> None:
    """Copy PR reference (org/repo#123) or branch name to clipboard."""
    item = self.highlighted_child
    if isinstance(item, PRRow):
        pr = item.pr
        value = f"{pr.repo_slug}#{pr.number}"
    elif isinstance(item, BranchRow):
        value = item.branch.name
    else:
        return
    try:
        await copy_to_clipboard(value)
        self.app.notify(f"Copied: {value}", severity="information")
    except ClipboardError as exc:
        self.app.notify(str(exc), severity="error")
```

4. Add `ClipboardError` import:
```python
from prdash.exceptions import ClipboardError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pr_list.py -k "copy_url or copy_ref" -v`
Expected: 5 PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x`
Expected: All tests pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/prdash/widgets/pr_list.py tests/test_pr_list.py
git commit -m "feat(widgets): add y/Y keybindings to copy PR URL and reference"
```

---

### Task 4: Update help screen and README

**Files:**
- Modify: `src/prdash/screens/help.py:19-24` (Actions section)
- Modify: `README.md:170-176` (Keybindings table)

- [ ] **Step 1: Update help screen**

In `src/prdash/screens/help.py`, add two entries to the "Actions" section (line 19-24), after the `("/", "Search / filter PRs")` entry:

```python
("y", "Copy PR URL"),
("Y", "Copy PR reference"),
```

- [ ] **Step 2: Update README keybindings table**

In `README.md`, after the `c` checkout row (line 170), add:

```markdown
| `y` | Copy selected PR URL to clipboard |
| `Y` | Copy PR reference (`org/repo#123`) or branch name |
```

- [ ] **Step 3: Verify help screen renders**

Run: `uv run pytest tests/test_pr_list.py -x` (sanity check — no help screen tests exist, but ensure no import breaks)
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/prdash/screens/help.py README.md
git commit -m "docs(keybindings): add y/Y clipboard copy to help screen and README"
```

---

### Task 5: Update WORK_TRACKER.md and final verification

**Files:**
- Modify: `WORK_TRACKER.md`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Manual smoke test**

Run: `uv run prdash`
1. Navigate to a PR, press `y` — toast shows full URL, verify with `pbpaste` in another terminal
2. Press `Y` — toast shows `org/repo#123`, verify with `pbpaste`
3. Navigate to a "Ready to PR" branch (if available), press `y`/`Y`
4. Navigate to a group header, press `y`/`Y` — nothing happens
5. Press `?` — help screen shows `y` and `Y` entries

- [ ] **Step 3: Update WORK_TRACKER.md**

Change T52 status from `not started` to `completed`.

- [ ] **Step 4: Commit**

```bash
git add WORK_TRACKER.md
git commit -m "docs(tasks): mark T52 as completed"
```

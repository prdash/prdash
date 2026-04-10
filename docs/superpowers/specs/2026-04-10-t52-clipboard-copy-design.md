# T52 - Copy PR URL/Number to Clipboard

## Context

Users frequently need to share PR links in chat or commit messages. Currently this requires opening the PR in a browser and copying from the address bar. Adding `y`/`Y` keybindings to copy PR URL or short reference directly from the dashboard removes this context switch.

## Design

### Clipboard Module (`src/prdash/clipboard.py`)

New async utility module with a single public function:

```python
async def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard via pbcopy (macOS)."""
```

- Pipes `text` to `pbcopy` via `asyncio.create_subprocess_exec` with stdin
- Encodes text as UTF-8 bytes for `proc.communicate(input=text.encode("utf-8"))`
- Raises `ClipboardError` if `pbcopy` is not found (`FileNotFoundError`) or the process exits non-zero
- macOS only (`pbcopy`) for now — all current users are on macOS; Linux support (`xclip`/`xsel`) deferred to a follow-up task

### Exception (`src/prdash/exceptions.py`)

Add `ClipboardError(DashboardError)` to the existing exception hierarchy.

### Keybindings (`src/prdash/widgets/pr_list.py`)

Two new bindings in `NavigableListView.BINDINGS`:

| Key | Binding name | Action |
|-----|-------------|--------|
| `y` | `copy_url` | Copy full URL |
| `Y` | `copy_ref` | Copy short reference |

### Action Methods (`NavigableListView`)

Follow the existing `action_checkout` pattern: `self.highlighted_child` + `isinstance` dispatch.

#### `action_copy_url`

| Item type | Copied value |
|-----------|-------------|
| `PRRow` | `pr.url` (full GitHub URL) |
| `BranchRow` | `branch.compare_url` (new-PR URL) |
| Other | No-op |

#### `action_copy_ref`

| Item type | Copied value |
|-----------|-------------|
| `PRRow` | `f"{pr.repo_slug}#{pr.number}"` (e.g. `org/repo#123`) |
| `BranchRow` | `branch.name` (branch name) |
| Other | No-op |

Both methods:
- Call `clipboard.copy_to_clipboard(value)`
- Show toast via `self.app.notify(f"Copied: {value}")` on success
- Show error toast on `ClipboardError`

### Help Screen (`src/prdash/screens/help.py`)

Add to the "Actions" section of `_KEYBINDINGS`:
- `("y", "Copy PR URL")`
- `("Y", "Copy PR reference")`

### README.md

Add `y`/`Y` to the keybindings documentation.

## Files Modified

| File | Changes |
|------|---------|
| `src/prdash/clipboard.py` | **New** — `copy_to_clipboard()` async function |
| `src/prdash/exceptions.py` | Add `ClipboardError` |
| `src/prdash/widgets/pr_list.py` | Add `y`/`Y` bindings and action methods |
| `src/prdash/screens/help.py` | Add keybinding entries |
| `README.md` | Add keybinding docs |
| `tests/test_clipboard.py` | **New** — clipboard module tests |
| `tests/test_pr_list.py` | Add action method tests |

## Tests

### `tests/test_clipboard.py`

- Happy path: mock subprocess, verify `pbcopy` called with correct stdin
- `pbcopy` not found: `FileNotFoundError` raises `ClipboardError`
- Non-zero exit: returncode 1 raises `ClipboardError`

### `tests/test_pr_list.py` (additions)

- Copy URL for PR: verify `pr.url` copied, toast shown
- Copy ref for PR: verify `repo_slug#number` copied
- Copy URL for branch: verify `compare_url` copied
- Copy ref for branch: verify `branch.name` copied
- No-op on group header/empty item: no clipboard call, no toast

## Verification

1. Run `uv run pytest tests/test_clipboard.py tests/test_pr_list.py -v` — all tests pass
2. Run `uv run prdash`, navigate to a PR, press `y` — toast shows full URL, verify in clipboard with `pbpaste`
3. Press `Y` — toast shows `org/repo#123`, verify with `pbpaste`
4. Navigate to a "Ready to PR" branch, press `y` — compare URL copied
5. Press `Y` — branch name copied
6. Navigate to a group header, press `y`/`Y` — nothing happens (no crash, no toast)

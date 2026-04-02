---
title: "T74 — PR Row Layout Restructure with Fixed-Width Columns"
date: 2026-04-02
status: draft
---

# T74 — PR Row Layout Restructure

## Context

The current PR row layout concatenates metadata inline with `·` separators (`@alice · 2d · CI:pass · Rev:ok · +350/-120 · 5💬`). This produces ragged, hard-to-scan rows because text labels vary in length. This redesign restructures rows into a two-line layout with fixed-width right-aligned status columns, inspired by gh-dash, creating clean vertical alignment across all rows.

## Design

### Row Layout

Each PR row is exactly 2 lines tall (no wrapping):

- **Line 1 (metadata, dim):** `repo/name #123 by @author · 2d ago` — left-aligned, dim text
- **Line 2 (title, bold):** PR title — left-aligned, bold, with inline badges (DRAFT, CONFLICT, BLOCKED, BEHIND)

Right-aligned on line 1, fixed-width status columns in this order (left to right):
- Size indicator `+N/-N` (~12 chars, green/red, abbreviated at 1000+)
- Comment count icon + number (~4 chars)
- CI status icon (1 char, colored)
- Review status icon (1 char, colored)

The ordering puts the most actionable indicators (CI, Review) at the rightmost edge for quick scanning. **Note:** This deviates from the T74 task spec which lists `CI, Review, Size, Comments`. The reordering was a deliberate design choice confirmed during brainstorming — the most-glanced-at indicators should be closest to the eye's resting point on the right edge. T74.md should be updated to match.

### Concrete Markup Templates

**Line 1 (metadata + status):**
```python
# Left content (dim metadata)
meta_line = f"[dim]{repo_prefix}#{pr.number} by @{escape(pr.author)} · {pr.age_display} ago[/dim]"
# where repo_prefix = f"{escape(pr.repo_slug)} " if pr.repo_slug else ""

# Right content (status icons)
status_col = f"{size} {comments} {ci} {review}"
# e.g.: "+1.2k/-800 5✉ ✓ ○"
```

**Line 2 (title + badges):**
```python
title_line = f"[bold]{escape(pr.title)}[/bold]{draft_badge}{merge_badge}"
# where draft_badge = " [cyan]DRAFT[/cyan]" if pr.is_draft else ""
# where merge_badge = _MERGE_STATE_BADGES.get(pr.merge_state_status, "")
```

This migrates `repo_slug` from the current title line to the metadata line, and adds `#number` and `ago` suffix which are not in the current implementation.

### Icon Constants

Replace text labels (`CI:pass`, `Rev:ok`) with Unicode icons, defined in a single `ICONS` dict for easy swapping by T75 (Nerd Font support):

```python
ICONS = {
    "ci_passing": "[green]✓[/green]",
    "ci_failing": "[red]✗[/red]",
    "ci_pending": "[yellow]◍[/yellow]",
    "ci_none": "[dim]–[/dim]",
    "review_approved": "[green]✓[/green]",
    "review_changes": "[red]✗[/red]",
    "review_pending": "[yellow]○[/yellow]",
    "review_none": "[dim]–[/dim]",
    "comment": "✉",
}
```

Merge state badges remain as text on line 2: `CONFLICT` (red), `BLOCKED` (yellow), `BEHIND` (yellow).

The comment icon changes from `💬` (emoji, double-width in many terminals) to `✉` (Unicode, single-width) for reliable fixed-column alignment.

### Size Abbreviation

New helper `_fmt_size(n)` abbreviates large numbers:
- `0` → `"0"`
- `42` → `"42"`
- `999` → `"999"`
- `1000` → `"1.0k"`
- `1200` → `"1.2k"`
- `15000` → `"15k"`

### Widget Structure (Approach A)

`PRRow.compose()` yields a `Horizontal` container with three children:

1. **Marker `Static`** (width 2): `●` for new PRs, space otherwise
2. **Left `Static`** (width `1fr`, class `pr-row-label`): metadata line + title line
3. **Right `Static`** (fixed width ~24, class `pr-row-status`): status columns, right-aligned

**Background highlight classes** (`pr-row-approved`, `pr-row-ready-to-merge`) are applied to the `Horizontal` container (class `pr-row-container`), not just the left `Static`. This ensures the green background tint spans the full row width including the status column. The `pr-row-new` class remains on the left `Static` since it only affects text style/color.

### BranchRow

Same three-widget structure for consistency. The right status column is empty (branches don't have CI/review/size), but still rendered so left content width matches PR rows.

### Truncation

Textual's `Static` doesn't support CSS `text-overflow: ellipsis`. To guarantee rows are exactly 2 lines tall:

1. **CSS constraint:** Set `height: 2` on `.pr-row-label` with `overflow: hidden`. This hard-caps the widget at 2 lines and clips any overflow.
2. **No Python-side truncation for v1.** The CSS clipping is sufficient to prevent layout breakage. Adding `…` ellipsis would require knowing the rendered width at compose time (not available) or hooking into resize events (added complexity for marginal benefit).
3. **Future refinement:** If ellipsis is desired later, it can be added via a `watch_size` handler that re-renders with truncated text.

### CSS Changes

```tcss
/* Modified — left content fixed at 2 lines, clips overflow */
.pr-row-label {
    padding: 0 1 0 0;
    height: 2;
    width: 1fr;
    overflow: hidden;
}

/* NEW — right-aligned status column, fixed width */
.pr-row-status {
    width: 24;
    height: 2;
    text-align: right;
}
```

Existing styles for `.pr-row-container`, `.pr-row-marker`, `.pr-row-new` are unchanged. `.pr-row-approved` and `.pr-row-ready-to-merge` selectors change from `.pr-row-approved` to target the container: `.pr-row-container.pr-row-approved`.

## Files to Modify

| File | Changes |
|------|---------|
| `src/prdash/widgets/pr_list.py` | Replace `_CI_LABELS`/`_REVIEW_LABELS` with `ICONS` dict, add `_fmt_size()`, restructure `PRRow.compose()` and `BranchRow.compose()` to three-widget Horizontal layout, move highlight classes to container |
| `src/prdash/app.tcss` | Add `.pr-row-status` rule, change `.pr-row-label` to `height: 2; overflow: hidden`, update `.pr-row-approved`/`.pr-row-ready-to-merge` selectors to target container |
| `tests/test_pr_list.py` | Update text assertions for new layout, add icon and size tests |

## Testing

### Existing tests to update
- CI/review label assertions → check for icon characters in `.pr-row-status`
- Multiline check → metadata on line 1 (dim, with `#number`), title on line 2 (bold)
- Draft badge → check on title line (line 2)
- Metadata separator patterns → `#number by @author · 2d ago` format
- Approved/ready-to-merge CSS class checks → verify class on container, not label

### Existing tests unchanged
- Navigation (j/k, arrows), group collapse/expand, approved-by-me sorting, checkout, filter visibility

### New tests
- Each CI/review state → correct icon in `.pr-row-status`
- `_fmt_size()` unit tests: 0→"0", 42→"42", 999→"999", 1000→"1.0k", 1200→"1.2k", 15000→"15k"
- Comment count: 0 → no icon shown, 5 → `5✉`
- BranchRow yields empty `.pr-row-status`

## Verification

1. `uv run pytest tests/test_pr_list.py` — all tests pass
2. `uv run prdash` — visual inspection: rows are 2 lines, status columns aligned, badges visible
3. Verify approved-by-me (green bg) and ready-to-merge (green bg) highlights span full row width
4. Test with long PR titles to confirm CSS clipping (no wrapping beyond 2 lines)
5. Test with large PRs to confirm size abbreviation (`+1.2k/-800`)

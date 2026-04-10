"""PR list widget with flat ListView and keyboard navigation."""

from __future__ import annotations

import asyncio
import webbrowser

from rich.markup import escape
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, ListItem, ListView, Static

from prdash.clipboard import copy_to_clipboard
from prdash.exceptions import ClipboardError
from prdash.models import CandidateBranch, PullRequest, QueryGroupResult
from prdash.state import get_collapsed_groups, set_collapsed_groups

_MERGE_STATE_BADGES: dict[str, str] = {
    "DIRTY": " [red]CONFLICT[/red]",
    "BLOCKED": " [yellow]BLOCKED[/yellow]",
    "BEHIND": " [yellow]BEHIND[/yellow]",
}

UNICODE_ICONS: dict[str, str] = {
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

NERD_ICONS: dict[str, str] = {
    "ci_passing": "[green]\U0000f058[/green]",
    "ci_failing": "[red]\U000f0159[/red]",
    "ci_pending": "[yellow]\U0000e641[/yellow]",
    "ci_none": "[dim]–[/dim]",
    "review_approved": "[green]\U000f012c[/green]",
    "review_changes": "[red]\U0000eb43[/red]",
    "review_pending": "[yellow]○[/yellow]",
    "review_none": "[dim]–[/dim]",
    "comment": "\U0000f27b",
}

# Active icon set — switched at startup by set_nerd_font()
ICONS: dict[str, str] = UNICODE_ICONS


def set_nerd_font(enabled: bool) -> None:
    """Switch the active icon set between Unicode and Nerd Font glyphs."""
    global ICONS
    ICONS = NERD_ICONS if enabled else UNICODE_ICONS


def _fmt_size(n: int) -> str:
    """Abbreviate large line counts: 1200 -> '1.2k', 15000 -> '15k'."""
    if n < 1000:
        return str(n)
    k = n / 1000
    if k < 10:
        return f"{k:.1f}k"
    return f"{int(k)}k"


class PRSelected(Message):
    """Emitted when a PR is highlighted in the list."""

    def __init__(self, pull_request: PullRequest) -> None:
        self.pull_request = pull_request
        super().__init__()


class GroupHeaderItem(ListItem):
    """A collapsible group header in the flat list."""

    def __init__(self, group_name: str, count: int, collapsed: bool = False, **kwargs: object) -> None:
        self.group_name = group_name
        self.count = count
        self.collapsed = collapsed
        super().__init__(**kwargs)

    @property
    def _arrow(self) -> str:
        return "▶" if self.collapsed else "▼"

    def compose(self):
        yield Static(
            f"{self._arrow} {self.group_name} ({self.count})",
            classes="group-header-label",
        )

    def refresh_label(self) -> None:
        """Update the displayed arrow after toggling collapsed state."""
        label = self.query_one(".group-header-label", Static)
        label.update(f"{self._arrow} {self.group_name} ({self.count})")


class EmptyGroupItem(ListItem):
    """Placeholder shown when an expanded group has no PRs."""

    def compose(self):
        yield Static("    No pull requests found", classes="empty-group-label")


class PRRow(ListItem):
    """A single PR row in the list."""

    def __init__(self, pr: PullRequest, is_new: bool = False, approved_by_me: bool = False, ready_to_merge: bool = False, **kwargs: object) -> None:
        self.pr = pr
        self.is_new = is_new
        self.approved_by_me = approved_by_me
        self.ready_to_merge = ready_to_merge
        super().__init__(**kwargs)

    def compose(self):
        marker_text = "[bold]●[/bold]" if self.is_new else " "

        # Left content: metadata (line 1) + title (line 2)
        repo_prefix = f"{escape(self.pr.repo_slug)} " if self.pr.repo_slug else ""
        meta_markup = f"[dim]{repo_prefix}#{self.pr.number} by @{escape(self.pr.author)}[/dim]"

        draft_badge = " [cyan]DRAFT[/cyan]" if self.pr.is_draft else ""
        merge_badge = _MERGE_STATE_BADGES.get(self.pr.merge_state_status, "")
        title_markup = f"[bold]{escape(self.pr.title)}[/bold]{draft_badge}{merge_badge}"

        # Right content: age + status icons
        age = f"[dim]{self.pr.age_display}[/dim]"
        size_segment = f"[green]+{_fmt_size(self.pr.additions)}[/green][dim]/[/dim][red]-{_fmt_size(self.pr.deletions)}[/red]"
        comment_segment = f" {self.pr.comment_count}{ICONS['comment']}" if self.pr.comment_count else ""
        ci_icon = ICONS.get(f"ci_{self.pr.ci_status}", ICONS["ci_none"])
        review_icon = ICONS.get(f"review_{self.pr.review_status}", ICONS["review_none"])
        status_col = f"{age} {size_segment}{comment_segment} {ci_icon} {review_icon}"

        # CSS classes
        title_classes = "pr-row-title"
        if self.is_new:
            title_classes += " pr-row-new"
        container_classes = "pr-row-container"
        if self.approved_by_me:
            container_classes += " pr-row-approved"
        if self.ready_to_merge:
            container_classes += " pr-row-ready-to-merge"

        with Vertical(classes=container_classes):
            with Horizontal(classes="pr-row-line1"):
                yield Static(marker_text, classes="pr-row-marker")
                yield Static(meta_markup, classes="pr-row-meta")
                yield Static(status_col, classes="pr-row-status")
            yield Static(title_markup, classes=title_classes)


class BranchSelected(Message):
    """Emitted when a candidate branch is highlighted in the list."""

    def __init__(self, branch: CandidateBranch) -> None:
        self.branch = branch
        super().__init__()


class BranchRow(ListItem):
    """A single candidate branch row in the list."""

    def __init__(self, branch: CandidateBranch, **kwargs: object) -> None:
        self.branch = branch
        super().__init__(**kwargs)

    def compose(self):
        repo_prefix = f"{escape(self.branch.repo_slug)} " if self.branch.repo_slug else ""
        meta_markup = f"[dim]{repo_prefix}[/dim]"
        title_markup = f"[bold]{escape(self.branch.name)}[/bold] · [cyan]ready to PR[/cyan]"

        age = f"[dim]{self.branch.age_display}[/dim]"
        with Vertical(classes="pr-row-container"):
            with Horizontal(classes="pr-row-line1"):
                yield Static(" ", classes="pr-row-marker")
                yield Static(meta_markup, classes="pr-row-meta")
                yield Static(age, classes="pr-row-status")
            yield Static(title_markup, classes="pr-row-title")


class NavigableListView(ListView):
    """ListView with j/k vim-style navigation and checkout action."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("c", "checkout", "Checkout", show=False),
        Binding("y", "copy_url", "Copy URL", show=False),
        Binding("Y", "copy_ref", "Copy Ref", show=False),
    ]

    async def action_checkout(self) -> None:
        """Checkout the selected PR branch or candidate branch."""
        item = self.highlighted_child
        if isinstance(item, PRRow):
            pr = item.pr
            cmd = ["gh", "pr", "checkout", str(pr.number)]
            if pr.repo_slug:
                cmd.extend(["--repo", pr.repo_slug])
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    self.app.notify(f"Checked out #{pr.number}", severity="information")
                else:
                    err = stderr.decode().strip() if stderr else "unknown error"
                    self.app.notify(f"Checkout failed: {err}", severity="error")
            except FileNotFoundError:
                self.app.notify("gh CLI not found — install it to use checkout", severity="error")
        elif isinstance(item, BranchRow):
            branch = item.branch
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "checkout", branch.name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    self.app.notify(f"Checked out {branch.name}", severity="information")
                else:
                    err = stderr.decode().strip() if stderr else "unknown error"
                    self.app.notify(f"Checkout failed: {err}", severity="error")
            except FileNotFoundError:
                self.app.notify("git not found", severity="error")

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


class PRListWidget(Widget):
    """Left-pane widget displaying PRs in a single flat ListView."""

    BINDINGS = [
        Binding("slash", "toggle_filter", "Search", show=False),
    ]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._groups: list[QueryGroupResult] = []
        self._header_states: dict[str, bool] = {}
        self._persisted_collapsed: set[str] = get_collapsed_groups()
        self._seen_ids: set[str] | None = None
        self._username: str | None = None
        self._filter_query: str = ""
        self._sort_mode: str = "age_newest"

    def compose(self):
        yield Input(placeholder="Filter PRs...", id="pr-filter-input", classes="hidden")
        yield NavigableListView(id="pr-list-view")

    def action_toggle_filter(self) -> None:
        """Show/hide the filter input."""
        filter_input = self.query_one("#pr-filter-input", Input)
        if "hidden" in filter_input.classes:
            filter_input.remove_class("hidden")
            filter_input.value = self._filter_query
            filter_input.focus()
        else:
            filter_input.add_class("hidden")
            self.query_one(NavigableListView).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the PR list as user types."""
        if event.input.id == "pr-filter-input":
            self._filter_query = event.value
            self._rebuild_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Hide input on Enter but keep filter active."""
        if event.input.id == "pr-filter-input":
            event.input.add_class("hidden")
            self.query_one(NavigableListView).focus()

    def _on_key_filter_escape(self, event) -> None:
        """Clear filter and hide input on Escape."""
        filter_input = self.query_one("#pr-filter-input", Input)
        if "hidden" not in filter_input.classes:
            self._filter_query = ""
            filter_input.value = ""
            filter_input.add_class("hidden")
            self._rebuild_list()
            self.query_one(NavigableListView).focus()
            event.prevent_default()
            event.stop()
            return True
        return False

    def _matches_filter(self, pr: PullRequest) -> bool:
        """Check if a PR matches the current filter query."""
        if not self._filter_query:
            return True
        q = self._filter_query.lower()
        return (
            q in pr.title.lower()
            or q in pr.author.lower()
            or q in pr.repo_slug.lower()
            or q in str(pr.number)
        )

    def _sort_prs(self, prs: list[PullRequest]) -> list[PullRequest]:
        """Sort PRs according to the current sort mode.

        Default (age_newest) preserves API order since GitHub already returns
        newest first. Other modes use stable sort to preserve original ordering
        for items with equal keys.
        """
        match self._sort_mode:
            case "age_newest":
                return prs  # GitHub API already returns newest first
            case "age_oldest":
                return sorted(prs, key=lambda pr: pr.created_at)
            case "ci_failing":
                order = {"failing": 0, "pending": 1, "passing": 2, "none": 3}
                return sorted(prs, key=lambda pr: order.get(pr.ci_status, 3))
            case "review_changes":
                order = {"changes_requested": 0, "pending": 1, "approved": 2, "none": 3}
                return sorted(prs, key=lambda pr: order.get(pr.review_status, 3))
            case "size_smallest":
                return sorted(prs, key=lambda pr: pr.additions + pr.deletions)
            case _:
                return prs

    def _matches_filter_branch(self, branch: CandidateBranch) -> bool:
        """Check if a branch matches the current filter query."""
        if not self._filter_query:
            return True
        q = self._filter_query.lower()
        return q in branch.name.lower() or q in branch.repo_slug.lower()

    def update_data(self, groups: list[QueryGroupResult], seen_ids: set[str] | None = None, username: str | None = None) -> None:
        """Rebuild the widget tree with new PR data."""
        self._groups = groups
        self._seen_ids = seen_ids
        self._username = username
        # Initialize header states for new groups; preserve existing collapse state
        for group in groups:
            if group.group_name not in self._header_states:
                if group.group_name in self._persisted_collapsed:
                    self._header_states[group.group_name] = True
                else:
                    self._header_states[group.group_name] = (
                        len(group.pull_requests) == 0 and len(group.branches) == 0
                    )
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Clear and repopulate the ListView from current groups and collapse state."""
        list_view = self.query_one("#pr-list-view", NavigableListView)

        # Record currently highlighted item identity for cursor preservation
        current_id: str | None = None
        if list_view.highlighted_child is not None:
            item = list_view.highlighted_child
            if isinstance(item, GroupHeaderItem):
                current_id = f"header:{item.group_name}"
            elif isinstance(item, PRRow):
                current_id = f"pr:{item.pr.id}"
            elif isinstance(item, BranchRow):
                current_id = f"branch:{item.branch.name}"

        list_view.clear()

        items: list[ListItem] = []
        item_ids: list[str] = []

        for i, group in enumerate(self._groups):
            collapsed = self._header_states.get(group.group_name, False)
            # Count will be updated after filtering below
            header = GroupHeaderItem(
                group.group_name, len(group.pull_requests) + len(group.branches), collapsed=collapsed,
            )
            if i == 0:
                header.add_class("first-group")
            items.append(header)
            item_ids.append(f"header:{group.group_name}")

            # Apply filter
            filtered_prs = [pr for pr in group.pull_requests if self._matches_filter(pr)]
            filtered_branches = [b for b in group.branches if self._matches_filter_branch(b)]

            # Skip entire group if filter is active and nothing matches
            if self._filter_query and not filtered_prs and not filtered_branches:
                items.pop()  # Remove the header we just added
                item_ids.pop()
                continue

            if not collapsed:
                if not filtered_prs and not filtered_branches:
                    items.append(EmptyGroupItem())
                    item_ids.append(f"empty:{group.group_name}")
                else:
                    prs = self._sort_prs(filtered_prs)
                    # Sort approved-by-me PRs to bottom in non-authored groups (after primary sort)
                    should_mark_approved = bool(self._username) and group.group_type != "authored"
                    if should_mark_approved:
                        prs = sorted(prs, key=lambda pr: pr.is_approved_by(self._username))  # type: ignore[arg-type]
                    for pr in prs:
                        is_new = bool(self._seen_ids) and pr.id not in self._seen_ids
                        approved_by_me = should_mark_approved and pr.is_approved_by(self._username)  # type: ignore[arg-type]
                        ready_to_merge = group.group_type == "authored" and pr.ready_to_merge
                        items.append(PRRow(pr, is_new=is_new, approved_by_me=approved_by_me, ready_to_merge=ready_to_merge))
                        item_ids.append(f"pr:{pr.id}")
                    for branch in filtered_branches:
                        items.append(BranchRow(branch))
                        item_ids.append(f"branch:{branch.name}")

        for item in items:
            list_view.append(item)

        # Restore cursor position or set initial index
        if current_id is None and items:
            list_view.index = 0
        elif current_id is not None and current_id in item_ids:
            list_view.index = item_ids.index(current_id)
        elif current_id is not None:
            # Item was removed (collapsed); find its group header
            group_name = current_id.split(":", 1)[1] if current_id.startswith("pr:") else None
            if group_name:
                # Find which group this PR belonged to
                for group in self._groups:
                    for pr in group.pull_requests:
                        if pr.id == group_name:
                            header_id = f"header:{group.group_name}"
                            if header_id in item_ids:
                                list_view.index = item_ids.index(header_id)
                            break

    def _persist_collapse_state(self) -> None:
        """Save current collapsed groups to disk."""
        collapsed = {name for name, is_collapsed in self._header_states.items() if is_collapsed}
        self._persisted_collapsed = collapsed
        set_collapsed_groups(collapsed)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Toggle collapse on group headers when selected (Enter pressed)."""
        if isinstance(event.item, GroupHeaderItem):
            header = event.item
            header.collapsed = not header.collapsed
            self._header_states[header.group_name] = header.collapsed
            self._persist_collapse_state()
            self._rebuild_list()
        elif isinstance(event.item, EmptyGroupItem):
            pass  # No-op for empty placeholder
        elif isinstance(event.item, PRRow):
            webbrowser.open(event.item.pr.url)
        elif isinstance(event.item, BranchRow):
            webbrowser.open(event.item.branch.compare_url)

    def on_key(self, event) -> None:
        """Handle special keys: Escape (clear filter), left/right (collapse/expand)."""
        if event.key == "escape":
            if self._on_key_filter_escape(event):
                return
            return
        if event.key not in ("left", "right"):
            return
        list_view = self.query_one("#pr-list-view", NavigableListView)
        item = list_view.highlighted_child
        if not isinstance(item, GroupHeaderItem):
            return
        if event.key == "left" and not item.collapsed:
            item.collapsed = True
            self._header_states[item.group_name] = True
            self._persist_collapse_state()
            self._rebuild_list()
            event.prevent_default()
            event.stop()
        elif event.key == "right" and item.collapsed:
            item.collapsed = False
            self._header_states[item.group_name] = False
            self._persist_collapse_state()
            self._rebuild_list()
            event.prevent_default()
            event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Emit PRSelected or BranchSelected when a row is highlighted."""
        if event.item is not None and isinstance(event.item, PRRow):
            self.post_message(PRSelected(event.item.pr))
        elif event.item is not None and isinstance(event.item, BranchRow):
            self.post_message(BranchSelected(event.item.branch))

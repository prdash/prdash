"""PR list widget with flat ListView and keyboard navigation."""

from __future__ import annotations

import webbrowser

from rich.markup import escape
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.containers import Horizontal
from textual.widgets import ListItem, ListView, Static

from prdash.models import CandidateBranch, PullRequest, QueryGroupResult
from prdash.state import get_collapsed_groups, set_collapsed_groups

_CI_LABELS = {
    "passing": "[green]CI:pass[/green]",
    "failing": "[red]CI:fail[/red]",
    "pending": "[yellow]CI:pend[/yellow]",
    "none": "[dim]CI:--[/dim]",
}
_REVIEW_LABELS = {
    "approved": "[green]Rev:ok[/green]",
    "changes_requested": "[red]Rev:chg[/red]",
    "pending": "[yellow]Rev:pend[/yellow]",
    "none": "[dim]Rev:--[/dim]",
}
_MERGE_STATE_BADGES: dict[str, str] = {
    "DIRTY": " · [red]CONFLICT[/red]",
    "BLOCKED": " · [yellow]BLOCKED[/yellow]",
    "BEHIND": " · [yellow]BEHIND[/yellow]",
}


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
        ci_label = _CI_LABELS.get(self.pr.ci_status, "[dim]CI:--[/dim]")
        review_label = _REVIEW_LABELS.get(self.pr.review_status, "[dim]Rev:--[/dim]")
        marker_text = "[bold]●[/bold]" if self.is_new else " "
        repo_prefix = f"[dim]{escape(self.pr.repo_slug)}[/dim]  " if self.pr.repo_slug else ""
        title_line = f"{repo_prefix}{escape(self.pr.title)}"
        draft_segment = " · [cyan]DRAFT[/cyan]" if self.pr.is_draft else ""
        merge_badge = _MERGE_STATE_BADGES.get(self.pr.merge_state_status, "")
        size_segment = f" · [green]+{self.pr.additions}[/green][dim]/[/dim][red]-{self.pr.deletions}[/red]"
        comment_segment = f" · [dim]{self.pr.comment_count}💬[/dim]" if self.pr.comment_count else ""
        meta_line = f"[dim]@{escape(self.pr.author)} · {self.pr.age_display}[/dim]{draft_segment}{merge_badge} · {ci_label} · {review_label}{size_segment}{comment_segment}"
        classes = "pr-row-label pr-row-new" if self.is_new else "pr-row-label"
        if self.approved_by_me:
            classes += " pr-row-approved"
        if self.ready_to_merge:
            classes += " pr-row-ready-to-merge"
        with Horizontal(classes="pr-row-container"):
            yield Static(marker_text, classes="pr-row-marker")
            yield Static(f"{title_line}\n{meta_line}", classes=classes)


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
        repo_prefix = f"[dim]{escape(self.branch.repo_slug)}[/dim]  " if self.branch.repo_slug else ""
        title_line = f"{repo_prefix}{escape(self.branch.name)}"
        meta_line = f"[dim]{self.branch.age_display}[/dim] · [cyan]ready to PR[/cyan]"
        with Horizontal(classes="pr-row-container"):
            yield Static(" ", classes="pr-row-marker")
            yield Static(f"{title_line}\n{meta_line}", classes="pr-row-label")


class NavigableListView(ListView):
    """ListView with j/k vim-style navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class PRListWidget(Widget):
    """Left-pane widget displaying PRs in a single flat ListView."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._groups: list[QueryGroupResult] = []
        self._header_states: dict[str, bool] = {}
        self._persisted_collapsed: set[str] = get_collapsed_groups()
        self._seen_ids: set[str] | None = None
        self._username: str | None = None

    def compose(self):
        yield NavigableListView(id="pr-list-view")

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
            total_count = len(group.pull_requests) + len(group.branches)
            header = GroupHeaderItem(
                group.group_name, total_count, collapsed=collapsed,
            )
            if i == 0:
                header.add_class("first-group")
            items.append(header)
            item_ids.append(f"header:{group.group_name}")

            if not collapsed:
                if not group.pull_requests and not group.branches:
                    items.append(EmptyGroupItem())
                    item_ids.append(f"empty:{group.group_name}")
                else:
                    prs = group.pull_requests
                    # Sort approved-by-me PRs to bottom in non-authored groups
                    should_mark_approved = bool(self._username) and group.group_type != "authored"
                    if should_mark_approved:
                        prs = sorted(prs, key=lambda pr: pr.is_approved_by(self._username))  # type: ignore[arg-type]
                    for pr in prs:
                        is_new = bool(self._seen_ids) and pr.id not in self._seen_ids
                        approved_by_me = should_mark_approved and pr.is_approved_by(self._username)  # type: ignore[arg-type]
                        ready_to_merge = group.group_type == "authored" and pr.ready_to_merge
                        items.append(PRRow(pr, is_new=is_new, approved_by_me=approved_by_me, ready_to_merge=ready_to_merge))
                        item_ids.append(f"pr:{pr.id}")
                    for branch in group.branches:
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
        """Handle left/right arrow keys for group header collapse/expand."""
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

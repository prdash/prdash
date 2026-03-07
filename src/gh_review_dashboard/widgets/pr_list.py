"""PR list widget with flat ListView and keyboard navigation."""

from __future__ import annotations

import webbrowser

from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from gh_review_dashboard.models import PullRequest, QueryGroupResult

_CI_ICONS = {"passing": "*", "failing": "!", "pending": "~", "none": " "}
_REVIEW_ICONS = {
    "approved": "+",
    "changes_requested": "x",
    "pending": "?",
    "none": " ",
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
        return ">" if self.collapsed else "v"

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

    def __init__(self, pr: PullRequest, is_new: bool = False, **kwargs: object) -> None:
        self.pr = pr
        self.is_new = is_new
        super().__init__(**kwargs)

    def compose(self):
        ci = _CI_ICONS.get(self.pr.ci_status, " ")
        review = _REVIEW_ICONS.get(self.pr.review_status, " ")
        new_marker = "● " if self.is_new else "  "
        label = (
            f"{new_marker}[{ci}][{review}] {self.pr.title}  "
            f"{self.pr.author}  {self.pr.age_display}"
        )
        classes = "pr-row-label pr-row-new" if self.is_new else "pr-row-label"
        yield Static(label, classes=classes)


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
        self._seen_ids: set[str] | None = None

    def compose(self):
        yield NavigableListView(id="pr-list-view")

    def update_data(self, groups: list[QueryGroupResult], seen_ids: set[str] | None = None) -> None:
        """Rebuild the widget tree with new PR data."""
        self._groups = groups
        self._seen_ids = seen_ids
        # Initialize header states for new groups; preserve existing collapse state
        for group in groups:
            if group.group_name not in self._header_states:
                self._header_states[group.group_name] = len(group.pull_requests) == 0
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

        list_view.clear()

        items: list[ListItem] = []
        item_ids: list[str] = []

        for group in self._groups:
            collapsed = self._header_states.get(group.group_name, False)
            header = GroupHeaderItem(
                group.group_name, len(group.pull_requests), collapsed=collapsed,
            )
            items.append(header)
            item_ids.append(f"header:{group.group_name}")

            if not collapsed:
                if not group.pull_requests:
                    items.append(EmptyGroupItem())
                    item_ids.append(f"empty:{group.group_name}")
                else:
                    for pr in group.pull_requests:
                        is_new = bool(self._seen_ids) and pr.id not in self._seen_ids
                        items.append(PRRow(pr, is_new=is_new))
                        item_ids.append(f"pr:{pr.id}")

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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Toggle collapse on group headers when selected (Enter pressed)."""
        if isinstance(event.item, GroupHeaderItem):
            header = event.item
            header.collapsed = not header.collapsed
            self._header_states[header.group_name] = header.collapsed
            self._rebuild_list()
        elif isinstance(event.item, EmptyGroupItem):
            pass  # No-op for empty placeholder
        elif isinstance(event.item, PRRow):
            webbrowser.open(event.item.pr.url)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Emit PRSelected when a PR row is highlighted."""
        if event.item is not None and isinstance(event.item, PRRow):
            self.post_message(PRSelected(event.item.pr))

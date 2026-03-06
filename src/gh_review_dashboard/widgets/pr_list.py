"""PR list widget with collapsible groups."""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, ListItem, ListView, Static

from gh_review_dashboard.models import PullRequest, QueryGroupResult

_CI_ICONS = {"passing": "*", "failing": "!", "pending": "~", "none": " "}
_REVIEW_ICONS = {
    "approved": "+",
    "changes_requested": "x",
    "pending": "?",
    "none": " ",
}


class PRSelected(Message):
    """Emitted when a PR is selected in the list."""

    def __init__(self, pull_request: PullRequest) -> None:
        self.pull_request = pull_request
        super().__init__()


class PRRow(ListItem):
    """A single PR row in the list."""

    def __init__(self, pr: PullRequest, **kwargs: object) -> None:
        self.pr = pr
        super().__init__(**kwargs)

    def compose(self):
        ci = _CI_ICONS.get(self.pr.ci_status, " ")
        review = _REVIEW_ICONS.get(self.pr.review_status, " ")
        label = (
            f"[{ci}][{review}] {self.pr.title}  "
            f"{self.pr.author}  {self.pr.age_display}"
        )
        yield Static(label, classes="pr-row-label")


class PRListWidget(Widget):
    """Left-pane widget displaying PRs grouped by query group."""

    def compose(self):
        yield VerticalScroll(id="pr-list-scroll")

    def update_data(self, groups: list[QueryGroupResult]) -> None:
        """Rebuild the widget tree with new PR data."""
        scroll = self.query_one("#pr-list-scroll", VerticalScroll)
        scroll.remove_children()

        for group in groups:
            count = len(group.pull_requests)
            title = f"{group.group_name} ({count})"
            collapsed = count == 0

            rows = [PRRow(pr) for pr in group.pull_requests]
            list_view = ListView(*rows)

            collapsible = Collapsible(
                list_view,
                title=title,
                collapsed=collapsed,
            )
            scroll.mount(collapsible)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Emit PRSelected when a row is highlighted."""
        if event.item is not None and isinstance(event.item, PRRow):
            self.post_message(PRSelected(event.item.pr))

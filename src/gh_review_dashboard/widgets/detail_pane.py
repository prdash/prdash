"""Detail pane widget for showing selected PR information."""

from __future__ import annotations

from datetime import UTC, datetime

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Markdown, Static

from gh_review_dashboard.models import PullRequest

_CHECK_ICONS = {"SUCCESS": "*", "FAILURE": "!", None: "~"}


def _relative_time(dt: datetime) -> str:
    """Return a short relative time string like '2d ago'."""
    delta = datetime.now(UTC) - dt
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 60:
        return f"{max(total_minutes, 1)}m ago"
    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"{total_hours}h ago"
    total_days = total_hours // 24
    if total_days < 7:
        return f"{total_days}d ago"
    return f"{total_days // 7}w ago"


def _format_metadata(pr: PullRequest) -> str:
    return (
        f"{pr.title} (#{pr.number})\n"
        f"by {pr.author} | opened {pr.age_display} ago\n"
        f"{pr.url}"
    )


def _format_description(pr: PullRequest) -> str:
    return pr.body or "*No description provided.*"


def _format_labels(pr: PullRequest) -> str:
    return ", ".join(pr.labels) if pr.labels else "None"


def _format_reviewers(pr: PullRequest) -> str:
    if not pr.reviewers:
        return "None"
    lines = []
    for r in pr.reviewers:
        lines.append(f"  {r.login:<20} {r.state}")
    return "\n".join(lines)


def _format_checks(pr: PullRequest) -> str:
    if not pr.checks:
        return "None"
    lines = []
    for c in pr.checks:
        icon = _CHECK_ICONS.get(c.conclusion, "~")
        conclusion_str = c.conclusion or ""
        lines.append(f"  {icon} {c.name:<25} {c.status}  {conclusion_str}")
    return "\n".join(lines)


def _format_timeline(pr: PullRequest) -> str:
    allowed = {"IssueComment", "PullRequestReview", "HeadRefForcePushed"}
    events = [e for e in pr.timeline_events if e.type in allowed]
    if not events:
        return "None"
    lines = []
    for e in events:
        rel = _relative_time(e.created_at)
        if e.type == "HeadRefForcePushed":
            lines.append(f"  [{rel}] {e.author} pushed (force)")
        elif e.type == "PullRequestReview":
            body_str = f"\n    {e.body}" if e.body else ""
            lines.append(f"  [{rel}] {e.author} reviewed{body_str}")
        else:
            body_str = f"\n    {e.body}" if e.body else ""
            lines.append(f"  [{rel}] {e.author} commented:{body_str}")
    return "\n".join(lines)


class ScrollableDetailScroll(VerticalScroll):
    """VerticalScroll with j/k vim-style scrolling."""

    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]


class DetailPaneWidget(Widget):
    """Right-pane widget showing selected PR details."""

    def compose(self):
        with ScrollableDetailScroll(id="detail-scroll"):
            yield Static(
                "Select a pull request from the list\nto view its details.",
                id="detail-placeholder",
            )
            yield Static("", id="detail-metadata", classes="hidden detail-section")
            yield Markdown("", id="detail-description", classes="hidden detail-section")
            yield Static("", id="detail-labels", classes="hidden detail-section")
            yield Static("", id="detail-reviewers", classes="hidden detail-section")
            yield Static("", id="detail-checks", classes="hidden detail-section")
            yield Static("", id="detail-timeline", classes="hidden detail-section")

    def show_pr(self, pr: PullRequest) -> None:
        """Display details for the given PR."""
        self.query_one("#detail-placeholder").add_class("hidden")

        sections = {
            "#detail-metadata": _format_metadata(pr),
            "#detail-labels": f"--- Labels ---\n{_format_labels(pr)}",
            "#detail-reviewers": f"--- Reviewers ---\n{_format_reviewers(pr)}",
            "#detail-checks": f"--- CI Checks ---\n{_format_checks(pr)}",
            "#detail-timeline": f"--- Timeline ---\n{_format_timeline(pr)}",
        }
        for selector, text in sections.items():
            widget = self.query_one(selector, Static)
            widget.update(text)
            widget.remove_class("hidden")

        desc_widget = self.query_one("#detail-description", Markdown)
        desc_content = f"---\n### Description\n\n{_format_description(pr)}"
        desc_widget.update(desc_content)
        desc_widget.remove_class("hidden")

    def clear(self) -> None:
        """Show the empty/placeholder state."""
        self.query_one("#detail-placeholder").remove_class("hidden")
        for widget in self.query(".detail-section"):
            widget.add_class("hidden")

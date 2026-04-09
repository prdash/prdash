"""Detail pane widget for showing selected PR information."""

from __future__ import annotations

from datetime import UTC, datetime

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Markdown, Static

from prdash.models import CandidateBranch, PullRequest, _format_age

_UNICODE_CHECK_ICONS: dict[str | None, str] = {"SUCCESS": "*", "FAILURE": "!", None: "~"}
_NERD_CHECK_ICONS: dict[str | None, str] = {"SUCCESS": "\U0000f058", "FAILURE": "\U000f0159", None: "\U0000e641"}

_UNICODE_REVIEWER_STATUS: dict[str, tuple[str, str]] = {
    "APPROVED": ("✓", "approved"),
    "CHANGES_REQUESTED": ("✗", "changes requested"),
    "PENDING": ("○", "pending"),
    "COMMENTED": ("💬", "commented"),
    "DISMISSED": ("—", "dismissed"),
}
_NERD_REVIEWER_STATUS: dict[str, tuple[str, str]] = {
    "APPROVED": ("\U000f012c", "approved"),
    "CHANGES_REQUESTED": ("\U0000eb43", "changes requested"),
    "PENDING": ("○", "pending"),
    "COMMENTED": ("\U0000f27b", "commented"),
    "DISMISSED": ("—", "dismissed"),
}

# Active icon sets — switched by set_detail_nerd_font()
_CHECK_ICONS: dict[str | None, str] = _UNICODE_CHECK_ICONS
_REVIEWER_STATUS: dict[str, tuple[str, str]] = _UNICODE_REVIEWER_STATUS


def set_detail_nerd_font(enabled: bool) -> None:
    """Switch the detail pane icon sets between Unicode and Nerd Font."""
    global _CHECK_ICONS, _REVIEWER_STATUS
    if enabled:
        _CHECK_ICONS = _NERD_CHECK_ICONS
        _REVIEWER_STATUS = _NERD_REVIEWER_STATUS
    else:
        _CHECK_ICONS = _UNICODE_CHECK_ICONS
        _REVIEWER_STATUS = _UNICODE_REVIEWER_STATUS


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


_MERGE_STATE_DISPLAY: dict[str, str] = {
    "DIRTY": " | Merge conflict",
    "BLOCKED": " | Merge blocked",
    "BEHIND": " | Behind base branch",
    "CLEAN": " | Ready to merge",
}


def _format_metadata(pr: PullRequest) -> str:
    title_prefix = f"{pr.repo_slug} " if pr.repo_slug else ""
    draft_indicator = " [Draft]" if pr.is_draft else ""
    comments_info = f" | {pr.comment_count} comments" if pr.comment_count else ""
    merge_info = _MERGE_STATE_DISPLAY.get(pr.merge_state_status, "")
    return (
        f"{title_prefix}{pr.title} (#{pr.number}){draft_indicator}\n"
        f"by {pr.author} | opened {pr.age_display} ago{comments_info}{merge_info}\n"
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
        icon, label = _REVIEWER_STATUS.get(r.state, ("?", r.state))
        lines.append(f"  {icon} {r.login} — {label}")
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


_FILE_STATUS_ICON = {
    "added": "+",
    "modified": "~",
    "removed": "-",
    "renamed": "→",
}


def _format_branch_commits(branch: CandidateBranch) -> str:
    """Format commit history for a candidate branch."""
    if not branch.commits:
        return ""
    lines = ["--- Commits ---"]
    for c in branch.commits:
        age = _format_age(c.authored_date)
        lines.append(f"  {c.short_sha} {c.message}  ({age} ago)")
    if branch.total_commits > len(branch.commits):
        remaining = branch.total_commits - len(branch.commits)
        lines.append(f"  … and {remaining} more")
    return "\n".join(lines)


def _format_branch_files(branch: CandidateBranch) -> str:
    """Format file change summary for a candidate branch."""
    if not branch.files:
        return ""
    lines = [
        f"--- Files ({branch.total_files} changed, "
        f"+{branch.total_additions} -{branch.total_deletions}) ---"
    ]
    for f in branch.files:
        icon = _FILE_STATUS_ICON.get(f.status, "?")
        lines.append(f"  {icon} +{f.additions} -{f.deletions}  {f.filename}")
    if branch.total_files > len(branch.files):
        remaining = branch.total_files - len(branch.files)
        lines.append(f"  … and {remaining} more")
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
            yield Static("", id="detail-metadata", classes="hidden detail-section", markup=False)
            yield Static("", id="detail-commits", classes="hidden detail-section", markup=False)
            yield Static("", id="detail-files", classes="hidden detail-section", markup=False)
            yield Static("", id="detail-reviewers", classes="hidden detail-section", markup=False)
            yield Markdown("", id="detail-description", classes="hidden detail-section")
            yield Static("", id="detail-labels", classes="hidden detail-section", markup=False)
            yield Static("", id="detail-checks", classes="hidden detail-section", markup=False)
            yield Static("", id="detail-timeline", classes="hidden detail-section", markup=False)

    def show_pr(self, pr: PullRequest) -> None:
        """Display details for the given PR."""
        self.query_one("#detail-placeholder").add_class("hidden")

        # Hide branch-specific sections
        for selector in ("#detail-commits", "#detail-files"):
            self.query_one(selector).add_class("hidden")

        sections = {
            "#detail-metadata": _format_metadata(pr),
            "#detail-reviewers": f"--- Reviewers ---\n{_format_reviewers(pr)}",
            "#detail-labels": f"--- Labels ---\n{_format_labels(pr)}",
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

    def show_branch(self, branch: CandidateBranch) -> None:
        """Display details for a candidate branch."""
        self.query_one("#detail-placeholder").add_class("hidden")

        metadata = (
            f"{branch.repo_slug} {branch.name}\n"
            f"last pushed {branch.age_display} ago\n"
            f"{branch.compare_url}"
        )
        meta_widget = self.query_one("#detail-metadata", Static)
        meta_widget.update(metadata)
        meta_widget.remove_class("hidden")

        # Commits section
        commits_text = _format_branch_commits(branch)
        commits_widget = self.query_one("#detail-commits", Static)
        if commits_text:
            commits_widget.update(commits_text)
            commits_widget.remove_class("hidden")
        else:
            commits_widget.add_class("hidden")

        # Files section
        files_text = _format_branch_files(branch)
        files_widget = self.query_one("#detail-files", Static)
        if files_text:
            files_widget.update(files_text)
            files_widget.remove_class("hidden")
        else:
            files_widget.add_class("hidden")

        desc_widget = self.query_one("#detail-description", Markdown)
        desc_widget.update("---\n### Description\n\n*No PR yet — press Enter to create one.*")
        desc_widget.remove_class("hidden")

        for selector in ("#detail-reviewers", "#detail-labels", "#detail-checks", "#detail-timeline"):
            self.query_one(selector).add_class("hidden")

    def clear(self) -> None:
        """Show the empty/placeholder state."""
        self.query_one("#detail-placeholder").remove_class("hidden")
        for widget in self.query(".detail-section"):
            widget.add_class("hidden")

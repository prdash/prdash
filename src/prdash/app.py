from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.timer import Timer
from textual import on, work
from textual.widgets import Footer, Header

from prdash.config import AppConfig
from prdash.exceptions import AuthError, GitHubAPIError, NetworkError
from prdash.github.client import GitHubClient
from prdash.models import PullRequest, QueryGroupResult, deduplicate_groups, reclassify_review_groups

_MAX_TOASTS_PER_REFRESH = 5
from prdash.screens.settings import SettingsScreen
from prdash.widgets import BranchSelected, DetailPaneWidget, PRListWidget, PRSelected


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "PR Dash"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "switch_pane", "Switch Pane"),
        Binding("r", "refresh", "Refresh"),
        Binding("S", "settings", "Settings"),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        github_client: GitHubClient | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.github_client = github_client
        self._seen_pr_ids: set[str] = set()
        self._previous_pr_map: dict[str, PullRequest] = {}
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PRListWidget(id="pr-list-pane")
            yield DetailPaneWidget(id="detail-pane")
        yield Footer()

    def _update_subtitle(self) -> None:
        """Update sub_title based on current config repos."""
        if self.config is None:
            return
        if self.config.repos:
            self.sub_title = ", ".join(self.config.repos)
        else:
            self.sub_title = "All repositories"

    def on_mount(self) -> None:
        """Set initial focus and start refresh cycle."""
        self.query_one("#pr-list-view").focus()
        self._update_subtitle()
        if self.github_client is not None and self.config is not None:
            self.refresh_data()
            self._refresh_timer = self.set_interval(
                self.config.poll_interval, self.refresh_data
            )

    def action_switch_pane(self) -> None:
        """Toggle focus between the PR list and detail scroll pane."""
        pr_list = self.query_one("#pr-list-view")
        detail_scroll = self.query_one("#detail-scroll")
        if pr_list.has_focus:
            detail_scroll.focus()
        else:
            pr_list.focus()

    def action_refresh(self) -> None:
        """Manual refresh triggered by keybinding."""
        self.refresh_data()

    @work(exclusive=True, group="refresh")
    async def refresh_data(self) -> None:
        """Fetch fresh data from GitHub and update the UI."""
        if self.github_client is None or self.config is None:
            return
        pr_list = self.query_one(PRListWidget)
        pr_list.loading = True
        try:
            groups, errors = await self.github_client.fetch_all_groups(self.config)
            groups = reclassify_review_groups(groups, self.config.username)
            groups = deduplicate_groups(groups)
            self._notify_changes(groups)
            pr_list.update_data(groups, seen_ids=self._seen_pr_ids, username=self.config.username)
            new_ids = {pr.id for group in groups for pr in group.pull_requests}
            self._seen_pr_ids = new_ids
            for group_name, exc in errors:
                self.notify(f"{group_name}: {exc}", severity="warning")
        except AuthError as e:
            self.notify(str(e), severity="error", timeout=10)
        except (NetworkError, GitHubAPIError) as e:
            self.notify(str(e), severity="warning", timeout=8)
        except Exception as e:
            self.notify(f"Unexpected error: {e}", severity="error", timeout=10)
        finally:
            pr_list.loading = False

    def _notify_changes(self, groups: list[QueryGroupResult]) -> None:
        """Detect and notify about meaningful changes since last refresh."""
        if not self._seen_pr_ids:
            return  # First load — skip notifications

        toasts: list[tuple[str, str]] = []  # (message, severity)

        # Detect new PRs per group
        for group in groups:
            new_in_group = [
                pr for pr in group.pull_requests if pr.id not in self._seen_pr_ids
            ]
            if new_in_group:
                count = len(new_in_group)
                noun = "PR" if count == 1 else "PRs"
                toasts.append(
                    (f"{count} new {noun} in {group.group_name}", "information")
                )

        # Detect CI and review status transitions
        new_pr_map: dict[str, PullRequest] = {}
        for group in groups:
            for pr in group.pull_requests:
                new_pr_map[pr.id] = pr

        for pr_id, new_pr in new_pr_map.items():
            old_pr = self._previous_pr_map.get(pr_id)
            if old_pr is None:
                continue
            # CI transitions
            if old_pr.ci_status != new_pr.ci_status:
                if new_pr.ci_status == "passing":
                    toasts.append(
                        (f"CI passed on {new_pr.repo_slug}#{new_pr.number}", "success")
                    )
                elif new_pr.ci_status == "failing":
                    toasts.append(
                        (f"CI failed on {new_pr.repo_slug}#{new_pr.number}", "warning")
                    )
            # Review transitions
            if old_pr.review_status != new_pr.review_status:
                if new_pr.review_status == "changes_requested":
                    toasts.append(
                        (f"Changes requested on {new_pr.repo_slug}#{new_pr.number}", "warning")
                    )
                elif new_pr.review_status == "approved":
                    toasts.append(
                        (f"Approved: {new_pr.repo_slug}#{new_pr.number}", "success")
                    )

        for msg, severity in toasts[:_MAX_TOASTS_PER_REFRESH]:
            self.notify(msg, severity=severity)  # type: ignore[arg-type]

        self._previous_pr_map = new_pr_map

    def action_settings(self) -> None:
        """Open the settings screen."""
        if self.config is not None:
            self.push_screen(SettingsScreen(self.config), callback=self._on_settings_result)

    def _on_settings_result(self, new_config: AppConfig | None) -> None:
        """Handle settings screen dismissal."""
        if new_config is None:
            return
        self.config = new_config
        self._update_subtitle()
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_interval(
            new_config.poll_interval, self.refresh_data
        )
        self.refresh_data()

    @on(PRSelected)
    def handle_pr_selected(self, event: PRSelected) -> None:
        self.query_one(DetailPaneWidget).show_pr(event.pull_request)

    @on(BranchSelected)
    def handle_branch_selected(self, event: BranchSelected) -> None:
        self.query_one(DetailPaneWidget).show_branch(event.branch)

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.timer import Timer
from textual import on, work
from textual.widgets import Footer, Header

from gh_review_dashboard.config import AppConfig
from gh_review_dashboard.exceptions import AuthError, GitHubAPIError, NetworkError
from gh_review_dashboard.github.client import GitHubClient
from gh_review_dashboard.models import deduplicate_groups
from gh_review_dashboard.screens.settings import SettingsScreen
from gh_review_dashboard.widgets import BranchSelected, DetailPaneWidget, PRListWidget, PRSelected


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "GitHub Review Dashboard"
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
        try:
            groups, errors = await self.github_client.fetch_all_groups(self.config)
            groups = deduplicate_groups(groups)
            pr_list = self.query_one(PRListWidget)
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

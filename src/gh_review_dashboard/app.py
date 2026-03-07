from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import on, work
from textual.widgets import Footer, Header

from gh_review_dashboard.config import AppConfig
from gh_review_dashboard.github.client import GitHubClient
from gh_review_dashboard.widgets import DetailPaneWidget, PRListWidget, PRSelected


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "GitHub Review Dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "switch_pane", "Switch Pane"),
        Binding("r", "refresh", "Refresh"),
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PRListWidget(id="pr-list-pane")
            yield DetailPaneWidget(id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        """Set initial focus and start refresh cycle."""
        self.query_one("#pr-list-view").focus()
        if self.github_client is not None and self.config is not None:
            self.refresh_data()
            self.set_interval(self.config.poll_interval, self.refresh_data)

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
        groups = await self.github_client.fetch_all_groups(self.config)
        pr_list = self.query_one(PRListWidget)
        pr_list.update_data(groups, seen_ids=self._seen_pr_ids)
        new_ids = {pr.id for group in groups for pr in group.pull_requests}
        self._seen_pr_ids = new_ids

    @on(PRSelected)
    def handle_pr_selected(self, event: PRSelected) -> None:
        self.query_one(DetailPaneWidget).show_pr(event.pull_request)

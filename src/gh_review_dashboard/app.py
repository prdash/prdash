from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import on
from textual.widgets import Footer, Header

from gh_review_dashboard.widgets import DetailPaneWidget, PRListWidget, PRSelected


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "GitHub Review Dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "switch_pane", "Switch Pane"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PRListWidget(id="pr-list-pane")
            yield DetailPaneWidget(id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        """Set initial focus to the PR list."""
        self.query_one("#pr-list-view").focus()

    def action_switch_pane(self) -> None:
        """Toggle focus between the PR list and detail scroll pane."""
        pr_list = self.query_one("#pr-list-view")
        detail_scroll = self.query_one("#detail-scroll")
        if pr_list.has_focus:
            detail_scroll.focus()
        else:
            pr_list.focus()

    @on(PRSelected)
    def handle_pr_selected(self, event: PRSelected) -> None:
        self.query_one(DetailPaneWidget).show_pr(event.pull_request)

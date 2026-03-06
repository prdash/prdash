from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual import on
from textual.widgets import Footer, Header

from gh_review_dashboard.widgets import DetailPaneWidget, PRListWidget, PRSelected


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "GitHub Review Dashboard"
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PRListWidget(id="pr-list-pane")
            yield DetailPaneWidget(id="detail-pane")
        yield Footer()

    @on(PRSelected)
    def handle_pr_selected(self, event: PRSelected) -> None:
        self.query_one(DetailPaneWidget).show_pr(event.pull_request)

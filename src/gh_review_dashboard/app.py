from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static


class ReviewDashboardApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "GitHub Review Dashboard"
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Static("PR List (placeholder)", id="pr-list-pane")
            yield Static("Detail (placeholder)", id="detail-pane")
        yield Footer()

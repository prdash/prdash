"""In-app settings screen for editing configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from gh_review_dashboard.config import AppConfig, QueryGroupConfig, save_config
from gh_review_dashboard.screens.query_groups import QueryGroupsScreen


class SettingsScreen(Screen[AppConfig | None]):
    """Settings screen for editing essential configuration fields.

    Dismisses with the new AppConfig on save, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    #settings-container { padding: 2 4; }
    .settings-field { margin-bottom: 1; }
    .settings-label { margin-bottom: 0; }
    .settings-buttons { margin-top: 1; dock: bottom; height: 3; }
    """

    def __init__(self, config: AppConfig, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._query_groups: list[QueryGroupConfig] = list(config.query_groups)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="settings-container"):
            yield Static("Settings", id="settings-title")
            yield Static("")

            yield Label("Repos (comma-separated, empty = all):", classes="settings-label")
            yield Input(
                value=", ".join(self._config.repos),
                id="repos-input",
                classes="settings-field",
            )

            yield Label("Username:", classes="settings-label")
            yield Input(
                value=self._config.username,
                id="username-input",
                classes="settings-field",
            )

            yield Label("Team slugs (comma-separated):", classes="settings-label")
            yield Input(
                value=", ".join(self._config.team_slugs),
                id="teams-input",
                classes="settings-field",
            )

            yield Label("Poll interval (seconds, min 30):", classes="settings-label")
            yield Input(
                value=str(self._config.poll_interval),
                id="interval-input",
                classes="settings-field",
            )

            yield Button("Query Groups...", id="query-groups-btn")

            yield Static("", id="error-msg")

            with Horizontal(classes="settings-buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "save-btn":
            self._save()
        elif event.button.id == "query-groups-btn":
            self.app.push_screen(
                QueryGroupsScreen(self._query_groups),
                callback=self._on_query_groups_result,
            )

    def _on_query_groups_result(
        self, result: list[QueryGroupConfig] | None
    ) -> None:
        if result is not None:
            self._query_groups = result

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        repos_text = self.query_one("#repos-input", Input).value.strip()
        username = self.query_one("#username-input", Input).value.strip()
        teams_text = self.query_one("#teams-input", Input).value.strip()
        interval_text = self.query_one("#interval-input", Input).value.strip()

        if not username:
            self.query_one("#error-msg", Static).update(
                "[bold red]Username is required.[/]"
            )
            return

        try:
            interval = int(interval_text)
        except ValueError:
            self.query_one("#error-msg", Static).update(
                "[bold red]Please enter a valid number for poll interval.[/]"
            )
            return

        if interval < 30:
            self.query_one("#error-msg", Static).update(
                "[bold red]Poll interval must be at least 30 seconds.[/]"
            )
            return

        repos = [s.strip() for s in repos_text.split(",") if s.strip()]
        team_slugs = [s.strip() for s in teams_text.split(",") if s.strip()]

        try:
            new_config = AppConfig(
                repos=repos,
                username=username,
                team_slugs=team_slugs,
                poll_interval=interval,
                query_groups=list(self._query_groups),
            )
        except Exception as e:
            self.query_one("#error-msg", Static).update(
                f"[bold red]{e}[/]"
            )
            return

        save_config(new_config)
        self.dismiss(new_config)

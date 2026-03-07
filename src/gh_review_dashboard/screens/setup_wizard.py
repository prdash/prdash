"""Setup wizard for first-run configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Static

from gh_review_dashboard.config import (
    DEFAULT_QUERY_GROUPS,
    AppConfig,
    RepoConfig,
    save_config,
)
from gh_review_dashboard.detect import (
    detect_repo_from_git_remote,
    detect_team_slugs,
    detect_username,
)


@dataclass
class WizardState:
    """Accumulates values across wizard steps."""

    org: str = ""
    repo_name: str = ""
    username: str = ""
    team_slugs: list[str] = field(default_factory=list)
    poll_interval: int = 300
    detected_team_slugs: list[str] = field(default_factory=list)
    completed: bool = False


class WizardStep(Screen):
    """Base class for wizard steps."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, state: WizardState, token: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.state = state
        self.token = token

    def action_cancel(self) -> None:
        self.app.exit()


class RepoScreen(WizardStep):
    """Step 1: Organization and repository name."""

    CSS = """
    #wizard-container { padding: 2 4; }
    .wizard-field { margin-bottom: 1; }
    .wizard-label { margin-bottom: 0; }
    .wizard-buttons { margin-top: 1; dock: bottom; height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wizard-container"):
            yield Static("Step 1 of 4: Repository", classes="wizard-label")
            yield Static("")
            yield Label("Organization:", classes="wizard-label")
            yield Input(
                value=self.state.org,
                placeholder="e.g. my-org",
                id="org-input",
                classes="wizard-field",
            )
            yield Label("Repository name:", classes="wizard-label")
            yield Input(
                value=self.state.repo_name,
                placeholder="e.g. my-repo",
                id="repo-input",
                classes="wizard-field",
            )
            yield Static("", id="error-msg")
            with Horizontal(classes="wizard-buttons"):
                yield Button("Next", variant="primary", id="next-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.exit()
            return
        if event.button.id == "next-btn":
            self._advance()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._advance()

    def _advance(self) -> None:
        org = self.query_one("#org-input", Input).value.strip()
        repo_name = self.query_one("#repo-input", Input).value.strip()

        if not org or not repo_name:
            self.query_one("#error-msg", Static).update(
                "[bold red]Both organization and repository name are required.[/]"
            )
            return

        self.state.org = org
        self.state.repo_name = repo_name
        self.app.push_screen(UsernameScreen(self.state, self.token))


class UsernameScreen(WizardStep):
    """Step 2: GitHub username."""

    CSS = """
    #wizard-container { padding: 2 4; }
    .wizard-field { margin-bottom: 1; }
    .wizard-label { margin-bottom: 0; }
    .wizard-buttons { margin-top: 1; dock: bottom; height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wizard-container"):
            yield Static("Step 2 of 4: Username", classes="wizard-label")
            yield Static("")
            yield Label("GitHub username:", classes="wizard-label")
            yield Input(
                value=self.state.username,
                placeholder="e.g. octocat",
                id="username-input",
                classes="wizard-field",
            )
            yield Static("", id="error-msg")
            with Horizontal(classes="wizard-buttons"):
                yield Button("Back", id="back-btn")
                yield Button("Next", variant="primary", id="next-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.exit()
        elif event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "next-btn":
            self._advance()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._advance()

    def _advance(self) -> None:
        username = self.query_one("#username-input", Input).value.strip()
        if not username:
            self.query_one("#error-msg", Static).update(
                "[bold red]Username is required.[/]"
            )
            return
        self.state.username = username
        self.app.push_screen(TeamSlugsScreen(self.state, self.token))


class TeamSlugsScreen(WizardStep):
    """Step 3: Team slugs (checkbox list or text input)."""

    CSS = """
    #wizard-container { padding: 2 4; }
    .wizard-field { margin-bottom: 1; }
    .wizard-label { margin-bottom: 0; }
    .wizard-buttons { margin-top: 1; dock: bottom; height: 3; }
    #teams-list { max-height: 12; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wizard-container"):
            yield Static("Step 3 of 4: Team Slugs", classes="wizard-label")
            yield Static("")

            if self.state.detected_team_slugs:
                yield Label("Select your teams:", classes="wizard-label")
                with Vertical(id="teams-list"):
                    for slug in self.state.detected_team_slugs:
                        checked = slug in self.state.team_slugs
                        yield Checkbox(slug, value=checked, id=f"team-{slug}")
            else:
                yield Label(
                    "No teams detected. Enter team slugs (comma-separated):",
                    classes="wizard-label",
                )
                yield Input(
                    value=", ".join(self.state.team_slugs),
                    placeholder="e.g. backend, frontend",
                    id="teams-input",
                    classes="wizard-field",
                )

            yield Static("", id="error-msg")
            with Horizontal(classes="wizard-buttons"):
                yield Button("Back", id="back-btn")
                yield Button("Next", variant="primary", id="next-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.exit()
        elif event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "next-btn":
            self._advance()

    def _advance(self) -> None:
        if self.state.detected_team_slugs:
            selected = []
            for slug in self.state.detected_team_slugs:
                cb = self.query_one(f"#team-{slug}", Checkbox)
                if cb.value:
                    selected.append(slug)
            self.state.team_slugs = selected
        else:
            text = self.query_one("#teams-input", Input).value.strip()
            self.state.team_slugs = [
                s.strip() for s in text.split(",") if s.strip()
            ]

        self.app.push_screen(PollIntervalScreen(self.state, self.token))


class PollIntervalScreen(WizardStep):
    """Step 4: Poll interval."""

    CSS = """
    #wizard-container { padding: 2 4; }
    .wizard-field { margin-bottom: 1; }
    .wizard-label { margin-bottom: 0; }
    .wizard-buttons { margin-top: 1; dock: bottom; height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wizard-container"):
            yield Static("Step 4 of 4: Poll Interval", classes="wizard-label")
            yield Static("")
            yield Label("Auto-refresh interval in seconds (minimum 30):", classes="wizard-label")
            yield Input(
                value=str(self.state.poll_interval),
                placeholder="300",
                id="interval-input",
                classes="wizard-field",
            )
            yield Static("", id="error-msg")
            with Horizontal(classes="wizard-buttons"):
                yield Button("Back", id="back-btn")
                yield Button("Finish", variant="primary", id="finish-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.exit()
        elif event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "finish-btn":
            self._finish()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._finish()

    def _finish(self) -> None:
        raw = self.query_one("#interval-input", Input).value.strip()
        try:
            interval = int(raw)
        except ValueError:
            self.query_one("#error-msg", Static).update(
                "[bold red]Please enter a valid number.[/]"
            )
            return

        if interval < 30:
            self.query_one("#error-msg", Static).update(
                "[bold red]Poll interval must be at least 30 seconds.[/]"
            )
            return

        self.state.poll_interval = interval

        config = AppConfig(
            repo=RepoConfig(org=self.state.org, name=self.state.repo_name),
            username=self.state.username,
            team_slugs=self.state.team_slugs,
            poll_interval=self.state.poll_interval,
            query_groups=list(DEFAULT_QUERY_GROUPS),
        )
        save_config(config)
        self.state.completed = True
        self.app.exit()


class SetupWizardApp(App):
    """Standalone app for the first-run setup wizard."""

    TITLE = "GitHub Review Dashboard - Setup"

    def __init__(self, token: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.token = token
        self.wizard_state = WizardState()

    def on_mount(self) -> None:
        self._run_detection()

    @work(exclusive=True)
    async def _run_detection(self) -> None:
        """Auto-detect repo, username, and team slugs, then push first screen."""
        repo = detect_repo_from_git_remote()
        if repo:
            self.wizard_state.org, self.wizard_state.repo_name = repo

        username = await detect_username(self.token)
        if username:
            self.wizard_state.username = username

        if self.wizard_state.org and self.wizard_state.username:
            slugs = await detect_team_slugs(
                self.token,
                self.wizard_state.org,
                self.wizard_state.username,
            )
            self.wizard_state.detected_team_slugs = slugs
            self.wizard_state.team_slugs = list(slugs)

        self.push_screen(
            RepoScreen(self.wizard_state, self.token)
        )

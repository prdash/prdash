"""Help overlay screen showing keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_KEYBINDINGS = [
    ("Navigation", [
        ("j / ↓", "Move down"),
        ("k / ↑", "Move up"),
        ("Tab", "Switch pane"),
        ("Enter", "Open PR / toggle group"),
        ("← / →", "Collapse / expand group"),
    ]),
    ("Actions", [
        ("r", "Refresh data"),
        ("c", "Checkout PR branch"),
        ("/", "Search / filter PRs"),
        ("Ctrl+P", "Command palette"),
    ]),
    ("App", [
        ("S", "Settings"),
        ("?", "This help screen"),
        ("Escape", "Close overlay / clear filter"),
        ("q", "Quit"),
    ]),
]


class HelpScreen(ModalScreen[None]):
    """Modal overlay showing all keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 52;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpScreen .help-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    HelpScreen .help-section-title {
        text-style: bold underline;
        margin-top: 1;
    }

    HelpScreen .help-row {
        margin-left: 2;
    }

    HelpScreen .help-footer {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Keyboard Shortcuts", classes="help-title")
            for section_name, bindings in _KEYBINDINGS:
                yield Static(section_name, classes="help-section-title")
                for key, desc in bindings:
                    yield Static(f"  {key:<14} {desc}", classes="help-row")
            yield Static("Press ? or Esc to close", classes="help-footer")

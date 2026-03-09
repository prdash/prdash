"""Query group management screen for adding, removing, reordering, and toggling groups."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, Switch

from gh_review_dashboard.config import QueryGroupConfig, QueryGroupType


class _GroupRow(Static):
    """A single row representing a query group."""

    def __init__(self, group: QueryGroupConfig, index: int, total: int) -> None:
        super().__init__()
        self._group = group
        self._index = index
        self._total = total

    def compose(self) -> ComposeResult:
        with Horizontal(classes="group-row"):
            yield Switch(
                value=self._group.enabled,
                id=f"switch-{self._index}",
                classes="group-switch",
            )
            yield Label(
                self._group.name,
                classes="group-name",
            )
            yield Label(
                f"({self._group.type.value})",
                classes="group-type",
            )
            if self._group.type == QueryGroupType.LABEL and self._group.labels:
                yield Label(
                    f"[{', '.join(self._group.labels)}]",
                    classes="group-labels",
                )
            with Horizontal(classes="group-actions"):
                yield Button(
                    "Up",
                    id=f"up-{self._index}",
                    classes="group-btn",
                    disabled=self._index == 0,
                )
                yield Button(
                    "Down",
                    id=f"down-{self._index}",
                    classes="group-btn",
                    disabled=self._index == self._total - 1,
                )
                yield Button(
                    "Remove",
                    id=f"remove-{self._index}",
                    variant="error",
                    classes="group-btn",
                )


class QueryGroupsScreen(Screen[list[QueryGroupConfig] | None]):
    """Screen for managing query groups.

    Dismisses with updated list on save, None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    #qg-container { padding: 2 4; }
    .group-row { height: 3; align: left middle; }
    .group-switch { width: 8; }
    .group-name { width: auto; min-width: 16; padding: 0 1; }
    .group-type { width: auto; min-width: 16; padding: 0 1; color: $text-muted; }
    .group-labels { width: auto; padding: 0 1; color: $accent; }
    .group-actions { width: auto; height: 3; }
    .group-btn { min-width: 8; }
    #add-form { padding: 1 0; }
    #add-form.hidden { display: none; }
    .qg-buttons { margin-top: 1; dock: bottom; height: 3; }
    #group-list { height: auto; max-height: 70%; }
    """

    def __init__(self, query_groups: list[QueryGroupConfig], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._groups: list[QueryGroupConfig] = [
            QueryGroupConfig(
                type=g.type, name=g.name, labels=list(g.labels), enabled=g.enabled
            )
            for g in query_groups
        ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="qg-container"):
            yield Static("Query Groups", id="qg-title")
            yield Static("")
            yield VerticalScroll(*self._build_rows(), id="group-list")
            yield Button("Add Group", id="add-group-btn")
            with Vertical(id="add-form", classes="hidden"):
                yield Label("Type:")
                yield Select(
                    [(t.value, t) for t in QueryGroupType],
                    id="add-type-select",
                    value=QueryGroupType.DIRECT_REVIEWER,
                )
                yield Label("Name:")
                yield Input(id="add-name-input")
                yield Label("Labels (comma-separated):", id="add-labels-label")
                yield Input(id="add-labels-input")
                yield Button("Confirm Add", id="confirm-add-btn", variant="primary")
            with Horizontal(classes="qg-buttons"):
                yield Button("Save", variant="primary", id="qg-save-btn")
                yield Button("Cancel", id="qg-cancel-btn")
        yield Footer()

    def _build_rows(self) -> list[_GroupRow]:
        return [
            _GroupRow(g, i, len(self._groups))
            for i, g in enumerate(self._groups)
        ]

    def _rebuild_list(self) -> None:
        group_list = self.query_one("#group-list", VerticalScroll)
        group_list.remove_children()
        for row in self._build_rows():
            group_list.mount(row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "qg-cancel-btn":
            self.dismiss(None)
        elif btn_id == "qg-save-btn":
            self.dismiss(list(self._groups))
        elif btn_id == "add-group-btn":
            form = self.query_one("#add-form")
            form.remove_class("hidden")
        elif btn_id == "confirm-add-btn":
            self._add_group()
        elif btn_id.startswith("up-"):
            idx = int(btn_id.split("-", 1)[1])
            self._move_up(idx)
        elif btn_id.startswith("down-"):
            idx = int(btn_id.split("-", 1)[1])
            self._move_down(idx)
        elif btn_id.startswith("remove-"):
            idx = int(btn_id.split("-", 1)[1])
            self._remove(idx)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id or ""
        if switch_id.startswith("switch-"):
            idx = int(switch_id.split("-", 1)[1])
            old = self._groups[idx]
            self._groups[idx] = QueryGroupConfig(
                type=old.type,
                name=old.name,
                labels=list(old.labels),
                enabled=event.value,
            )

    def _move_up(self, idx: int) -> None:
        if idx > 0:
            self._groups[idx - 1], self._groups[idx] = (
                self._groups[idx],
                self._groups[idx - 1],
            )
            self._rebuild_list()

    def _move_down(self, idx: int) -> None:
        if idx < len(self._groups) - 1:
            self._groups[idx], self._groups[idx + 1] = (
                self._groups[idx + 1],
                self._groups[idx],
            )
            self._rebuild_list()

    def _remove(self, idx: int) -> None:
        if 0 <= idx < len(self._groups):
            self._groups.pop(idx)
            self._rebuild_list()

    def _add_group(self) -> None:
        group_type = self.query_one("#add-type-select", Select).value
        name = self.query_one("#add-name-input", Input).value.strip()
        labels_text = self.query_one("#add-labels-input", Input).value.strip()

        if not name or group_type is Select.BLANK:
            return

        labels: list[str] = []
        if group_type == QueryGroupType.LABEL and labels_text:
            labels = [l.strip() for l in labels_text.split(",") if l.strip()]

        self._groups.append(
            QueryGroupConfig(type=group_type, name=name, labels=labels, enabled=True)
        )

        # Reset form and hide
        self.query_one("#add-name-input", Input).value = ""
        self.query_one("#add-labels-input", Input).value = ""
        self.query_one("#add-form").add_class("hidden")
        self._rebuild_list()

    def action_cancel(self) -> None:
        self.dismiss(None)

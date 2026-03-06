# Textual TUI Reference

## App Structure

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

class DashboardApp(App):
    CSS_PATH = "dashboard.tcss"
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield PRListWidget(id="pr-list")
        yield DetailPaneWidget(id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.fetch_data()  # Kick off initial data load
```

## Widget Composition

```python
from textual.widget import Widget
from textual.containers import Horizontal, Vertical, ScrollableContainer

class PRListWidget(Widget):
    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            for group in self.groups:
                yield GroupSection(group, id=f"group-{group.name}")
```

- Use `Horizontal` / `Vertical` containers for layout
- Assign `id=` for CSS targeting and `query_one()` lookups
- Use `classes=` for shared styling (e.g., `classes="pr-row"`)

## CSS Patterns

```css
/* Split pane layout */
#main-container {
    layout: horizontal;
}
#pr-list {
    width: 40%;
}
#detail-pane {
    width: 60%;
}

/* Collapsible sections */
.group-section.collapsed .group-content {
    display: none;
}

/* Status indicators */
.ci-pass { color: green; }
.ci-fail { color: red; }
.ci-pending { color: yellow; }

/* Hide elements */
.hidden { display: none; }
```

- Use `%` for proportional widths, `fr` for flexible rows
- Use CSS variables for theming: `$accent`, `$primary`
- Textual CSS is a subset of CSS — check Textual docs for supported properties

## Message Passing

```python
from textual.message import Message

class PRSelected(Message):
    def __init__(self, pr: PullRequest) -> None:
        super().__init__()
        self.pr = pr

# In PRListWidget:
    def on_list_view_selected(self, event):
        self.post_message(PRSelected(event.item.pr))

# In DashboardApp:
    def on_pr_list_widget_pr_selected(self, message: PRSelected) -> None:
        self.query_one("#detail-pane").update_pr(message.pr)
```

- Messages bubble up from widget to app
- Handler naming: `on_{widget_snake}_{message_snake}`
- Alternative: `@on(PRSelected)` decorator for explicit binding

## Reactive Attributes

```python
from textual.reactive import reactive

class DetailPaneWidget(Widget):
    current_pr: reactive[PullRequest | None] = reactive(None)

    def watch_current_pr(self, pr: PullRequest | None) -> None:
        if pr:
            self.query_one("#pr-title").update(pr.title)
            # ... update other fields
```

- `reactive()` auto-triggers `watch_{name}` on change
- Use for state that should trigger UI updates

## Workers (Async Operations)

```python
from textual.worker import Worker, get_current_worker

class DashboardApp(App):
    @work(exclusive=True, group="refresh")
    async def fetch_data(self) -> None:
        """Fetch PR data in a background worker."""
        data = await self.github_client.fetch_all_groups(self.config.groups)
        # Update UI from worker — must use call_from_thread for sync methods
        self.call_from_thread(self.update_pr_list, data)
```

- `@work` runs the method in a Textual worker thread
- `exclusive=True` cancels previous worker in the same group
- Use `call_from_thread()` to safely update UI from worker context

## Timers (Auto-Refresh)

```python
def on_mount(self) -> None:
    self.set_interval(
        self.config.poll_interval,
        self.fetch_data,
        name="auto-refresh",
    )
```

- `set_interval` calls the callback repeatedly
- Timer name allows cancellation: `self.remove_timer("auto-refresh")`
- First fetch should happen immediately in `on_mount`, timer handles subsequent

## Key Bindings

```python
BINDINGS = [
    ("j", "cursor_down", "Down"),
    ("k", "cursor_up", "Up"),
    ("enter", "open_in_browser", "Open"),
    ("r", "refresh", "Refresh"),
    ("space", "toggle_group", "Toggle Group"),
]

def action_open_in_browser(self) -> None:
    if self.selected_pr:
        import webbrowser
        webbrowser.open(self.selected_pr.url)
```

- Bindings: `(key, action_name, description)`
- Action methods: `action_{name}()`
- Description appears in footer

## Pilot Testing

```python
@pytest.mark.asyncio
async def test_pr_list_shows_groups():
    app = DashboardApp(config=test_config, client=mock_client)
    async with app.run_test() as pilot:
        groups = pilot.app.query(".group-section")
        assert len(groups) == 3

async def test_keyboard_navigation():
    async with app.run_test() as pilot:
        await pilot.press("j")          # Navigate down
        await pilot.press("enter")      # Select
        await pilot.click("#refresh")   # Click button
```

## Pitfalls

- **No blocking I/O in `compose()` or `on_mount()`** — use workers for async ops
- **`call_from_thread()`** is required when updating UI from worker threads
- **Widget queries** return empty if called before mount completes
- **CSS file** must be in same directory as the Python module or use absolute path
- **`run_test()`** requires `size=(width, height)` param if layout depends on terminal size

# PR Dash

Terminal-based TUI dashboard for monitoring GitHub PRs requiring your attention.
Tech stack: Python, Textual (TUI), httpx + GitHub GraphQL API, Pydantic v2, TOML config, uv (packaging).

# Project Layout

```
src/prdash/                    # Main package
  __main__.py                  # Entry point (wizard/dashboard lifecycle)
  app.py                       # Textual App subclass
  config.py                    # TOML config loading/saving, Pydantic models
  detect.py                    # Auto-detection helpers (git remote, username, teams)
  models.py                    # PR data models (PullRequest, Reviewer, etc.)
  github/                      # GitHub API subpackage
    __init__.py                # Re-exports GitHubClient, build_search_query
    client.py                  # Async GraphQL client (GitHubClient)
    queries.py                 # GraphQL query template + search builder
  screens/                     # Textual Screen modules
    __init__.py                # Re-exports SetupWizardApp, SettingsScreen
    setup_wizard.py            # First-run 4-step setup wizard
    settings.py                # In-app settings screen (S keybinding)
  widgets/                     # Textual widget modules
    pr_list.py                 # Left pane: PR list with collapsible groups
    detail_pane.py             # Right pane: PR detail view
tests/                         # pytest tests mirroring src/ structure
tasks/                         # Task specs T01-T12
agent_docs/                    # Detailed reference docs (load on demand)
pyproject.toml                 # Project metadata and dependencies
```

# Work Tracking

- Read `WORK_TRACKER.md` for task overview, phases, and dependency graph
- Read `PRODUCT_GUIDELINES.md` for full feature requirements
- Before starting task N, read `tasks/T{NN}.md` for the complete spec
- Update `WORK_TRACKER.md` status to "in progress" when starting a task
- Update `WORK_TRACKER.md` status to "completed" when done and verified
- Check dependency column — do not start a task whose dependencies are incomplete
- **After completing and verifying a task, always commit all changes** (code, tests, config, `WORK_TRACKER.md`) before moving on to the next task
- **Keep documentation up to date**: If changes affect project structure, commands, conventions, or patterns described in `CLAUDE.md`, `README.md`, or files under `agent_docs/`, update those docs in the same commit. In particular, changes to features, keybindings, config fields, commands, or usage should be reflected in `README.md`
- **Creating new tasks**: Use `/new-task [idea]` to interactively create task specs and update the work tracker

# Commands

```bash
uv sync                                    # Install/update dependencies
uv run prdash                              # Run the app (or just `prdash` if globally installed)
uv run python -m prdash                    # Run the app (alternative)
uv run pytest                              # Run all tests
uv run pytest tests/test_config.py         # Run a specific test file
uv run pytest -x                           # Stop on first failure
uv run pytest -k "test_name"               # Run tests matching pattern
uv run mypy src/                           # Type checking (if configured)
```

# Commits

Use Conventional Commits format: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
Scopes: `config`, `auth`, `api`, `models`, `tui`, `widgets`, `tests`, `deps`

Examples:
- `feat(api): add GraphQL query for team review requests`
- `fix(config): handle missing TOML file with default config`
- `test(models): add PullRequest computed property tests`
- `refactor(widgets): extract PR row into separate component`
- `chore(deps): add httpx and respx dependencies`

# Engineering Principles

- **Dependency injection**: Pass clients and config as constructor args, never import globals
- **DRY**: Extract shared logic; avoid copy-pasting query builders or parsers
- **KISS**: Simplest approach that works; don't over-abstract early
- **Type hints**: All function signatures fully typed; use `TypeAlias` for complex types
- **Custom exceptions**: `DashboardError` base with `AuthError`, `ConfigError`, `GitHubAPIError`
- **Async**: Use `async def` + `await` for I/O; `asyncio.gather` for parallel queries
- **Immutability**: Prefer frozen Pydantic models for data; mutate only app state

# Testing

- Every module in `src/` should have a corresponding `tests/test_{module}.py`
- Test public interfaces, computed properties, error paths, and edge cases
- Mock external dependencies (HTTP, subprocess, filesystem) — never make real API calls
- Use `pytest-asyncio` for async tests, `tmp_path` for file fixtures
- Test Textual widgets with `async with app.run_test() as pilot:`
- For detailed patterns, fixtures, and examples: **read `agent_docs/testing.md`**

# Agent Docs (Progressive Context Loading)

Load these files only when working on relevant tasks. Do not read all at once.

## `agent_docs/testing.md`
- **Load when:** Writing or fixing tests (all tasks)
- **Contains:** pytest patterns, async testing, mocking (httpx, subprocess, filesystem), Textual pilot testing, shared fixtures, what NOT to test

## `agent_docs/github_api.md`
- **Load when:** Working on T03 (auth), T04 (GraphQL client), T10 (refresh), T11 (error handling)
- **Contains:** gh CLI auth, httpx AsyncClient setup, GraphQL query structure, response parsing, pagination, error handling, parallel queries

## `agent_docs/textual_tui.md`
- **Load when:** Working on T05 (app shell), T06 (PR list), T07 (detail pane), T08 (keybindings), T09 (browser action), T10 (refresh timer)
- **Contains:** App structure, widget composition, CSS patterns, message passing, reactive attributes, workers, timers, key bindings, pilot testing

## `agent_docs/data_models.md`
- **Load when:** Working on T02 (config), T04 (response parsing), T06/T07 (displaying PR data)
- **Contains:** Pydantic v2 patterns, config models, PR data models, computed properties, enums, validation, immutability

## `agent_docs/code_style.md`
- **Load when:** Creating new modules or reviewing code structure (all tasks)
- **Contains:** Module template, naming conventions, error hierarchy, dependency injection pattern, async conventions, file size guidelines

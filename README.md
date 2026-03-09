# GitHub Review Dashboard

Terminal-based TUI dashboard for monitoring GitHub pull requests that need your attention. Built with [Textual](https://textual.textualize.io/) for a rich terminal experience.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **[gh CLI](https://cli.github.com/)** — GitHub CLI, authenticated (`gh auth login`)

## Installation

### From source (development)

```bash
git clone https://github.com/your-org/gh-review-dashboard.git
cd gh-review-dashboard
uv sync
```

### Global install

```bash
uv tool install /path/to/gh-review-dashboard
```

This makes the `ghrd` command available globally.

## Quick Start

```bash
ghrd
```

Or, if running from the project directory without a global install:

```bash
uv run ghrd
```

On first run, a **setup wizard** walks you through configuration:

1. **Repository** — org and repo name (auto-detected from git remote if available)
2. **Username** — your GitHub username (auto-detected from your auth token)
3. **Teams** — team slugs for team review requests (auto-detected from GitHub API)
4. **Confirm** — review and save

After setup, the dashboard launches automatically.

## Configuration

Config file location: `~/.config/gh-review-dashboard/config.toml`

### Example config

```toml
username = "octocat"
team_slugs = ["frontend", "platform"]
poll_interval = 300
timeout = 30.0

[repo]
org = "my-org"
name = "my-repo"

[[query_groups]]
type = "direct_reviewer"
name = "Requested Reviewer"
enabled = true

[[query_groups]]
type = "team_reviewer"
name = "Team Reviewer"
enabled = true

[[query_groups]]
type = "mentioned"
name = "Mentioned/Involved"
enabled = true

[[query_groups]]
type = "authored"
name = "My PRs"
enabled = true

[[query_groups]]
type = "label"
name = "Labeled"
labels = ["needs-review"]
enabled = false
```

### Field reference

| Field | Type | Default | Description |
|---|---|---|---|
| `repo.org` | string | *(required)* | GitHub organization or owner |
| `repo.name` | string | *(required)* | Repository name |
| `username` | string | *(required)* | Your GitHub username |
| `team_slugs` | list[str] | `[]` | Team slugs for team review queries |
| `poll_interval` | int | `300` | Auto-refresh interval in seconds (min 30) |
| `timeout` | float | `30.0` | HTTP request timeout in seconds (min 1.0) |
| `query_groups` | list | 5 defaults | PR query groups (see below) |

#### Query group fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | string | *(required)* | One of the query group types below |
| `name` | string | *(required)* | Display name in the PR list |
| `labels` | list[str] | `[]` | Label filters (only for `label` type) |
| `enabled` | bool | `true` | Whether this group is active |

## Usage

```bash
ghrd
```

The dashboard has a split-pane layout:

- **Left pane** — PR list organized by query group, with collapsible sections showing title, author, age, CI status, and review status
- **Right pane** — Detail view for the selected PR with reviewers panel, Markdown description, labels, CI checks, and timeline

## Keybindings

| Key | Action |
|---|---|
| `j` / `Down` | Move cursor down in PR list |
| `k` / `Up` | Move cursor up in PR list |
| `Enter` | Toggle group collapse/expand, or open PR in browser |
| `Tab` | Switch focus between left and right panes |
| `r` | Refresh PR data |
| `S` | Open settings screen |
| `Escape` | Close settings / query groups screen |
| `q` | Quit |

## Query Groups

Query groups define which PRs appear in the dashboard. There are 5 types:

| Type | Description |
|---|---|
| `direct_reviewer` | PRs where you are directly requested as a reviewer |
| `team_reviewer` | PRs where one of your teams is requested for review |
| `mentioned` | PRs where you are mentioned or involved |
| `authored` | PRs you authored |
| `label` | PRs matching specific labels (set via `labels` field) |

PRs are deduplicated across groups — each PR appears only in its highest-priority group (priority follows the order listed above).

You can customize query groups by:

- **Adding/removing groups** in `config.toml` or via the in-app query groups screen
- **Reordering** to change display and deduplication priority
- **Toggling** `enabled` to hide groups without deleting them
- **Using labels** with the `label` type to track specific categories

## In-App Settings

Press `S` to open the settings screen where you can edit:

- Repository org and name
- Username
- Team slugs
- Poll interval

From settings, you can also open the **Query Groups** screen to add, remove, reorder, and toggle query groups. Changes are saved immediately and trigger a data refresh.

# PR Dash - Product Guidelines

## Overview

A terminal-based (TUI) dashboard for monitoring GitHub pull requests that require your attention. Built for personal use, focused on ensuring you never miss a review request in a large monorepo.

## Problem

Keeping track of review requests in a large monorepo is difficult. PRs where you are a requested reviewer, where your team is requested, where you are mentioned, or that match labels you care about can easily get lost in the noise. The current GitHub UI and email notifications are insufficient for staying on top of these.

## Tech Stack

- **Language**: Python
- **TUI Framework**: [Textual](https://github.com/Textualize/textual) (full TUI framework with widgets, layout, CSS)
- **GitHub API**: GraphQL API (more efficient, fewer requests)
- **Authentication**: `gh` CLI (already installed and configured; reuse its auth token)
- **Package Management**: `uv`
- **Configuration**: TOML file

## Features

### PR Query Groups

PRs are organized into configurable groups, each representing a reason the PR is relevant to you. Default groups:

1. **Directly Requested Reviewer** - You are personally requested as a reviewer
2. **Team Reviewer** - A team you belong to is requested to review
3. **Mentioned/Involved** - You are mentioned or otherwise involved
4. **My PRs** - PRs you authored
5. **Label-based** - PRs matching labels you configure

Groups are defined in the TOML config file with sensible defaults. Users can add, remove, or reorder groups.

### PR Information

Each PR in the list displays at a glance:

- PR title
- Author
- Age (time since creation)
- CI/check status
- Review status (approvals, changes requested, pending)

### Detail Pane

When a PR is selected, the detail pane shows:

- PR description/body
- Labels
- Requested reviewers and their status
- CI/check status (expanded)
- Event timeline (comments, reviews, pushes)

### Actions

- **Open in browser**: Open the selected PR in the default browser (primary action)
- This is a **read-only** dashboard; no approve/comment/reject from the TUI

### Refresh

- **Auto-refresh**: Polls GitHub at a configurable interval
- **Manual refresh**: Keybinding to trigger an immediate refresh
- **New item indicator**: Visual badge/indicator when new PRs appear since last viewed

## Configuration

TOML config file with sensible defaults. Configuration includes:

- **Repository**: Org and repo name
- **Query groups**: List of group definitions (type, label filters, enabled/disabled)
- **Poll interval**: Auto-refresh interval (configurable)
- **GitHub username**: For identifying "my" PRs and review requests
- **Team slugs**: Teams to monitor for team-based review requests

## Layout

**Split-pane layout**:

- **Left pane**: PR list organized by query group (collapsible sections)
- **Right pane**: Detail view for the currently selected PR (metadata summary, description, timeline)

## Keybindings

- `j` / `k` or Arrow keys: Navigate up/down in PR list
- `Enter`: Open selected PR in browser
- `r` or `R`: Manual refresh
- Standard Textual keybindings for pane navigation and quitting

## Non-Goals

- No inline diff viewing
- No review actions (approve, comment, request changes) from within the TUI
- Single repository focus (no multi-repo support initially)
- No desktop notifications (visual indicator within TUI only)

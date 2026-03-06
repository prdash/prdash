# Work Tracker

## Status Key

| Status | Meaning |
|---|---|
| not started | Work has not begun |
| in progress | Currently being worked on |
| blocked | Waiting on a dependency or decision |
| completed | Done and verified |

## Phase 1: Project Scaffolding

No dependencies. These tasks can be done in parallel.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T01 | Python project setup (`uv init`, pyproject.toml, directory structure, dependencies: textual, httpx) | none | completed |
| T02 | Configuration system (TOML config loading, schema with defaults, config model classes for repo, username, team slugs, poll interval, query groups) | none | not started |

## Phase 2: Data Layer

Depends on Phase 1.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T03 | GitHub authentication (extract token from `gh` CLI, validate token works) | T01 | not started |
| T04 | GraphQL client & queries (PR queries for each group type: direct reviewer, team reviewer, mentioned/involved, authored, label-based; response parsing into data models with title, author, age, CI status, review status, description, labels, reviewers, timeline) | T01, T02, T03 | not started |

## Phase 3: Core TUI

Depends on Phase 2.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T05 | App shell & layout (Textual app class, split-pane CSS layout with left/right panes, header/footer) | T01 | not started |
| T06 | PR list widget (left pane: collapsible sections per query group, PR row display with title, author, age, CI/check status, review status) | T04, T05 | not started |
| T07 | Detail pane widget (right pane: PR description/body, labels, requested reviewers and their status, expanded CI/check status, event timeline) | T04, T05 | not started |

## Phase 4: Interactivity

Depends on Phase 3.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T08 | Navigation & keybindings (vim j/k + arrow keys for list navigation, group collapse/expand, pane focus switching) | T06, T07 | not started |
| T09 | Open in browser action (Enter key opens selected PR URL in default browser) | T06, T08 | not started |
| T10 | Refresh system (auto-refresh on configurable timer from config, manual refresh via r/R keybinding, new-item visual indicator for PRs appearing since last viewed) | T04, T06, T08 | not started |

## Phase 5: Polish

Depends on Phase 4.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T11 | Error handling & edge cases (API errors, no PRs found, auth failures, network timeouts, graceful degradation) | T03, T04, T06, T07, T10 | not started |
| T12 | README & usage documentation (installation, configuration, usage, keybindings) | all prior tasks | not started |

## Feature Coverage

All features from PRODUCT_GUIDELINES.md are covered:

- **PR query groups** (5 types): T02 (config), T04 (queries)
- **PR information display** (title, author, age, CI, review status): T06
- **Detail pane** (description, labels, reviewers, CI, timeline): T07
- **Split-pane layout**: T05
- **Keybindings** (j/k, arrows, Enter, r/R): T08, T09
- **Open in browser**: T09
- **Refresh** (auto, manual, new-item indicator): T10
- **Configuration** (TOML, repo, username, teams, poll interval, groups): T02
- **Auth via `gh` CLI**: T03
- **Error handling**: T11
- **Documentation**: T12

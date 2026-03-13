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
| T02 | Configuration system (TOML config loading, schema with defaults, config model classes for repo, username, team slugs, poll interval, query groups) | none | completed |

## Phase 2: Data Layer

Depends on Phase 1.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T03 | GitHub authentication (extract token from `gh` CLI, validate token works) | T01 | completed |
| T04 | GraphQL client & queries (PR queries for each group type: direct reviewer, team reviewer, mentioned/involved, authored, label-based; response parsing into data models with title, author, age, CI status, review status, description, labels, reviewers, timeline) | T01, T02, T03 | completed |

## Phase 3: Core TUI

Depends on Phase 2.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T05 | App shell & layout (Textual app class, split-pane CSS layout with left/right panes, header/footer) | T01 | completed |
| T06 | PR list widget (left pane: collapsible sections per query group, PR row display with title, author, age, CI/check status, review status) | T04, T05 | completed |
| T07 | Detail pane widget (right pane: PR description/body, labels, requested reviewers and their status, expanded CI/check status, event timeline) | T04, T05 | completed |

## Phase 4: Interactivity

Depends on Phase 3.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T08 | Navigation & keybindings (vim j/k + arrow keys for list navigation, group collapse/expand, pane focus switching) | T06, T07 | completed |
| T09 | Open in browser action (Enter key opens selected PR URL in default browser) | T06, T08 | completed |
| T10 | Refresh system (auto-refresh on configurable timer from config, manual refresh via r/R keybinding, new-item visual indicator for PRs appearing since last viewed) | T04, T06, T08 | completed |

## Phase 5: Polish

Depends on Phase 4.

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T11 | Error handling & edge cases (API errors, no PRs found, auth failures, network timeouts, graceful degradation) | T03, T04, T06, T07, T10 | completed |
| T12 | README & usage documentation (installation, configuration, usage, keybindings) | all prior tasks | completed |
| T21 | Render PR description as Markdown in detail pane (use Textual's built-in Markdown widget) | T07 | completed |
| T22 | Prominent reviewers panel in detail pane (status icons, reorder above description) | T07, T21 | completed |

## Phase 6: Setup & Settings

Depends on Phase 2 (T02, T03).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T13 | Auto-detection helpers (git remote parsing, username from token, team slugs from API) | T03 | completed |
| T14 | Config serialization (save_config function, TOML writing, atomic save) | T02 | completed |
| T15 | Setup wizard screens (4-step Textual Screen wizard with auto-fill, validation) | T13, T14 | completed |
| T16 | Wizard lifecycle integration (launch wizard when no config exists, then start dashboard) | T15 | completed |
| T17 | In-app settings screen (S keybinding, edit essentials, immediate save + re-fetch) | T14, T15 | completed |
| T18 | Setup/settings polish (end-to-end tests, edge cases, documentation updates) | T16, T17 | completed |
| T19 | Query group settings screen (add/remove/reorder/toggle query groups in-app) | T17 | completed |

## Phase 7: Deduplication

Depends on Phase 3 (T06) and Phase 4 (T10).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T20 | Deduplicate PRs across query groups (assign each PR to highest-priority matching group, dedup at display layer) | T06, T10 | completed |

## Phase 8: Cross-Repo

Depends on Phase 2 (T02, T04), Phase 3 (T06, T07), Phase 6 (T15, T17).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T23 | Cross-repo support (default to all repos like github.com/pulls/review-requested, optional repo filters, repo slug in PR list + detail pane, config migration from single repo to repos list) | T04, T06, T07, T02, T15, T17 | completed |

## Phase 9: Distribution

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T24 | CLI entry point (`ghrd` command via `[project.scripts]`, global install via `uv tool install`) | T01 | completed |
| T31 | CLI distribution flags (`--version`, `--update` with install-method detection, end-user install docs) | T24 | not started |
| T32 | Homebrew tap distribution (formula, release workflow, tap repo setup, docs) | T31 | not started |

## Phase 10: PR List Polish

Depends on Phase 3 (T06).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T25 | PR list readability (colored Rich markup status labels, multi-line rows, group separators, triangle arrows) | T06 | completed |
| T26 | "Approved by me" visual differentiation (green background + sort-to-bottom for PRs user has approved) | T06 | completed |
| T27 | Fix PR title wrap indentation (restructure PRRow layout so wrapped title lines maintain indent) | T25 | completed |
| T28 | Group header focus highlight (subtle background tint when header row is focused) | T06 | completed |
| T29 | Arrow key collapse/expand for group headers (left=collapse, right=expand) | T06, T08 | completed |

## Phase 11: Branch Detection

Depends on Phase 2 (T04), Phase 3 (T06, T07).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T30 | "Ready to PR" branch detection (detect user's recent branches without open PRs, display as query group, Enter opens GitHub new-PR page) | T04, T06, T07 | completed |

## Feature Coverage

All features from PRODUCT_GUIDELINES.md are covered:

- **PR query groups** (5 types): T02 (config), T04 (queries)
- **PR information display** (title, author, age, CI, review status): T06
- **Detail pane** (description, labels, reviewers, CI, timeline): T07
- **Split-pane layout**: T05
- **Keybindings** (j/k, arrows, Enter, r/R): T08, T09
- **Open in browser**: T09
- **Refresh** (auto, manual, new-item indicator): T10
- **Configuration** (TOML, repo, username, teams, poll interval, groups): T02, T14
- **Auth via `gh` CLI**: T03
- **Setup wizard** (auto-detect, 4-step first-run): T13, T15, T16
- **In-app settings** (S key, edit + save + refresh): T17
- **Error handling**: T11
- **Documentation**: T12

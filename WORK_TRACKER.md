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
| T24 | CLI entry point (`prdash` command via `[project.scripts]`, global install via `uv tool install`) | T01 | completed |
| T31 | CLI distribution flags (`--version`, `--update` with install-method detection, end-user install docs) | T24 | completed |
| T32 | Homebrew tap distribution (formula, release workflow, tap repo setup, docs) | T31 | completed |
| T33 | Dynamic versioning via git tags (hatch-vcs, no manual version bumps, tag-based releases) | T31 | completed |

## Phase 10: PR List Polish

Depends on Phase 3 (T06).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T25 | PR list readability (colored Rich markup status labels, multi-line rows, group separators, triangle arrows) | T06 | completed |
| T26 | "Approved by me" visual differentiation (green background + sort-to-bottom for PRs user has approved) | T06 | completed |
| T27 | Fix PR title wrap indentation (restructure PRRow layout so wrapped title lines maintain indent) | T25 | completed |
| T28 | Group header focus highlight (subtle background tint when header row is focused) | T06 | completed |
| T29 | Arrow key collapse/expand for group headers (left=collapse, right=expand) | T06, T08 | completed |
| T36 | Draft PR badge — inline cyan DRAFT badge on PR list metadata line + detail pane indicator | T06, T07 | completed |
| T37 | Fix CI:pend bug — treat NEUTRAL/SKIPPED as passing, CANCELLED/TIMED_OUT/etc. as failing | T06 | completed |
| T38 | Green-highlight ready-to-merge PRs in "My PRs" using `mergeStateStatus` API field | T06, T07 | completed |
| T74 | PR row layout restructure with fixed-width columns (two-line rows, right-aligned status icons, ellipsis truncation) | T06, T49, T50, T51 | completed |
| T75 | Nerd Font icon support (configurable `nerd_font` toggle for richer glyphs) | T74 | not started |

## Phase 11: Branch Detection

Depends on Phase 2 (T04), Phase 3 (T06, T07).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T30 | "Ready to PR" branch detection (detect user's recent branches without open PRs, display as query group, Enter opens GitHub new-PR page) | T04, T06, T07 | completed |
| T34 | Fix "Ready to PR" for large repos (replace bulk refs query with Events API + GraphQL batch verification) | T30 | completed |
| T35 | Branch detail pane: commits & file changes (enrich candidate branches with compare API data, render in detail pane) | T30, T34 | completed |

## Phase 12: Navigation & Discoverability

Depends on Phase 3 (T05, T06), Phase 4 (T08).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T40 | Command Palette (Ctrl+P fuzzy command search) | T05 | completed |
| T41 | Help Overlay (`?` keybinding shows all shortcuts) | T05, T08 | completed |
| T42 | Fuzzy Search/Filter Bar (`/` to filter PRs by title/author/repo) | T06 | completed |
| T43 | PR Sort Options (sort within groups by age, CI, review, size) | T06, T40, T49 | completed |

## Phase 13: Polish & Feel

Depends on Phase 3 (T06), Phase 4 (T10), Phase 12 (T40).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T44 | Toast Notifications (detect new PRs, CI/review changes on refresh) | T10 | completed |
| T45 | Loading States (loading indicator during refresh) | T06, T10 | completed |
| T46 | Theme Support (Textual built-in themes, persist in config) | T40 | completed |
| T47 | Persistent Group Collapse State (save/restore across sessions) | T06 | completed |

## Phase 14: Workflow Actions

Depends on Phase 3 (T06).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T48 | One-Key PR Checkout (`c` to checkout PR branch via gh CLI) | T06 | completed |

## Phase 15: Data Enrichment

Depends on Phase 2 (T04), Phase 3 (T06, T07), Phase 10 (T38).

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T49 | PR Size Indicators (additions/deletions on PR rows) | T04, T06 | completed |
| T50 | Merge Conflict Badges (surface DIRTY/BLOCKED/BEHIND states) | T06, T38 | completed |
| T51 | Comment Count (total comments on PR rows and detail pane) | T04, T06, T07 | completed |

## Phase 16: Future — Workflow Actions

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T52 | Copy PR URL/Number to Clipboard (`y`/`Y` keybindings) | T06 | not started |
| T53 | Quick Approve + Merge (approve and/or merge via gh CLI) | T06, T48 | not started |
| T54 | Inline Diff Preview (show PR diff via gh pr diff + delta) | T06, T07 | not started |
| T55 | Custom User-Defined Shell Actions (templated commands in config) | T06, T48 | not started |
| T56 | Watch CI Checks Live (real-time CI polling for selected PR) | T07, T10 | not started |
| T57 | Open in Editor (open PR changed files in $EDITOR) | T06, T48 | not started |

## Phase 17: Future — Data & Features

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T58 | GitHub Notifications Integration (unread notifications section) | T04, T06 | not started |
| T59 | Review Wait Time / Stale Badge (time since review requested) | T04, T06 | not started |
| T60 | Linked Issues Display (show closingIssuesReferences) | T04, T07 | not started |
| T61 | Colored Label Badges (render labels with GitHub hex colors) | T04, T06, T07 | not started |
| T62 | Deployment Status (preview environment status on PRs) | T04, T07 | not started |
| T63 | Required Reviewers / CODEOWNERS Awareness | T04, T07 | not started |
| T64 | Auto-Merge Status / Toggle (show and enable auto-merge) | T04, T06 | not started |
| T65 | Comment Unread Indicator (track new comments since last view) | T51, T47 | not started |
| T66 | Issues Section (assigned/mentioned issues alongside PRs) | T04, T06 | not started |
| T67 | Stacked PR Awareness (detect PR dependency chains) | T04, T06 | not started |

## Phase 18: Future — UX & Polish

| ID | Task | Dependencies | Status |
|---|---|---|---|
| T68 | Multiple Layout Modes (list-only, detail-only, split toggle) | T05, T06, T07 | not started |
| T69 | Customizable Keybindings (user-defined key mappings in config) | T08, T02 | not started |
| T70 | Multiple Config Profiles (--config flag, profile switcher) | T02 | not started |
| T71 | Sparkline Activity Graph (mini activity visualization in detail) | T07 | not started |
| T72 | Web Mode via textual-serve (--web flag for browser access) | T05 | not started |
| T73 | Desktop OS Notifications (native notifications for new PRs) | T44 | not started |

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

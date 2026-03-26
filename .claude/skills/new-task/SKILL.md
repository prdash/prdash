---
name: new-task
description: Create a new task specification and add it to the work tracker backlog. Use when the user wants to plan, spec out, or add a new feature/fix/improvement to the project backlog.
argument-hint: "[brief idea or feature request]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git *), AskUserQuestion
---

# New Task Creation Workflow

You are creating a new task specification for the PR Dash project. Follow these steps carefully.

**IMPORTANT: No files should be touched or updated besides `WORK_TRACKER.md` and files under the `tasks/` directory.** Do not modify source code, tests, configuration, documentation, or any other project files during this workflow.

## Step 1 — Gather context

1. Read `WORK_TRACKER.md` to understand current phases, existing tasks, and find the **highest task ID** (scan all phase tables for the largest `T{NN}` number).
2. Read `PRODUCT_GUIDELINES.md` for product context and feature goals.
3. Parse `$ARGUMENTS` as the initial idea or feature request from the user.

## Step 2 — Explore & clarify

Think through the request from two perspectives:

- **Customer perspective**: What user value does this deliver? What problem does it solve? How will the user interact with it?
- **Code/workflow perspective**: What modules and files are likely affected? Are there existing patterns to follow? What are the technical constraints?

Then ask the user clarifying questions to remove ambiguities. Cover:
- Scope boundaries (what's in, what's out)
- Acceptance criteria (how do we know it's done?)
- Edge cases and error scenarios
- UX expectations (keybindings, visual layout, interactions)

If the idea is vague, help brainstorm: suggest concrete approaches, trade-offs, and alternatives.

**Continue asking questions until requirements are clear.** Use `AskUserQuestion` for each round of clarification. Do not proceed to writing files until the user confirms the requirements.

## Step 3 — Scope & decompose

- If the request is small enough for a single task, proceed as one task.
- If large, break it into multiple subtasks — each gets its own ID, spec file, and acceptance criteria.
- Identify dependencies between subtasks and on existing tasks.
- Propose the breakdown to the user for confirmation before writing any files.

## Step 4 — Determine placement

- Decide whether tasks fit in an existing phase in `WORK_TRACKER.md` or need a new phase section.
- Assign the next sequential task ID(s) after the current highest (e.g., if highest is T22, next is T23).

## Step 5 — Write task spec file(s)

Create `tasks/T{NN}.md` for each task, following this exact format:

```markdown
# T{NN} - {Title}

| Field        | Value          |
|--------------|----------------|
| **ID**       | T{NN}          |
| **Phase**    | {N} - {Name}   |
| **Dependencies** | {IDs or None} |
| **Status**   | not started    |

## Objective

{1-2 sentence summary of what this task accomplishes}

## Background

{Why this change is needed, current state, user impact}

## Requirements

1. {Concrete, specific requirement}
2. ...

## Files

| File | Changes |
|------|---------|
| `path/to/file.py` | Description of changes |

## Acceptance Criteria

- [ ] {Verifiable criterion}
- [ ] ...
```

## Step 6 — Update WORK_TRACKER.md

- Add task row(s) to the appropriate phase table in `WORK_TRACKER.md`.
- If creating a new phase, add it with a heading, description, dependency note, and table header matching existing format.
- Follow existing table format: `| ID | Task | Dependencies | Status |`
- Set status to `not started` for all new tasks.

## Step 7 — Commit

Stage only the new/modified files and commit:

```
git add tasks/T{NN}.md WORK_TRACKER.md
git commit -m "docs(tasks): add task spec T{NN} for {brief description}"
```

If multiple tasks were created:
```
git commit -m "docs(tasks): add task specs T{NN}-T{MM} for {brief description}"
```

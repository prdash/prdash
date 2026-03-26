# Review Group Reclassification + Assigned Group

**Date**: 2026-03-26
**Status**: Approved

## Problem

GitHub's `review-requested:{username}` search filter matches PRs where the user has **any** pending review request — including requests made to teams the user belongs to. This means the "Requested Reviewer" and "Team Reviewer" groups overlap 100%: every team-based request also appears in the direct reviewer group. The deduplication layer hides the overlap but the result is that "Team Reviewer" is always empty.

Additionally, there is no group for PRs where the user is assigned (the `assignee` mechanism is independent of review requests).

## Solution

### 1. Add `is_team` field to Reviewer model

**File**: `src/prdash/models.py`

```python
class Reviewer(BaseModel, frozen=True):
    login: str
    state: str
    is_team: bool = False
```

Update `_parse_reviewers()`:

- Change `reviewer_map` from `dict[str, str]` to `dict[str, tuple[str, bool]]` (login → (state, is_team))
- In the review-requests loop: if `requestedReviewer` has a `"login"` key → `is_team=False` (User). If it has a `"slug"` key (no `"login"`) → `is_team=True` (Team). The existing `requested.get("login") or requested.get("slug")` already branches on this.
- In the reviews loop: always set `is_team=False` (only users submit reviews, never teams). Team slugs and user logins are disjoint keys, so a review entry will never overwrite a team entry.
- When constructing the final `Reviewer` list, unpack `(state, is_team)` from the map.

### 2. Post-fetch reclassification

**New function** in `src/prdash/models.py`:

`reclassify_review_groups(groups: list[QueryGroupResult], username: str) -> list[QueryGroupResult]`:
- Find the `direct_reviewer` and `team_reviewer` groups in the results
- If either group is missing, return groups unchanged
- For each PR in the `direct_reviewer` group: check whether any reviewer has `is_team == False` AND `login == username`. If such a reviewer exists, the user was individually requested — keep the PR in `direct_reviewer`. If no such reviewer exists, the user was only requested via team membership — move the PR to `team_reviewer`.
- Deduplicate `team_reviewer` after receiving moved PRs (by PR id)

**Edge case**: If `team_slugs` config is empty, the `team_reviewer` group query returns no results but the group still exists in the results list. Reclassification can still move PRs into it. If the `team_reviewer` group doesn't exist at all (e.g., user disabled it), skip reclassification — leave PRs in `direct_reviewer` rather than losing them.

**Called in** `src/prdash/app.py`, between fetch and dedup:
```python
groups = await self.github_client.fetch_all_groups(self.config)
groups = reclassify_review_groups(groups, self.config.username)
groups = deduplicate_groups(groups)
```

### 3. New "Assigned" query group type

**File**: `src/prdash/config.py`

Add `ASSIGNED = "assigned"` to `QueryGroupType` enum.

**File**: `src/prdash/github/queries.py`

Add case to `build_search_query()`:
```python
case QueryGroupType.ASSIGNED:
    return [f"{p} assignee:{config.username}" for p in prefixes]
```

### 4. New default group order

**File**: `src/prdash/config.py`

```python
DEFAULT_QUERY_GROUPS = [
    QueryGroupConfig(type=QueryGroupType.READY_TO_PR, name="Ready to PR"),
    QueryGroupConfig(type=QueryGroupType.AUTHORED, name="My PRs"),
    QueryGroupConfig(type=QueryGroupType.DIRECT_REVIEWER, name="Requested Reviewer"),
    QueryGroupConfig(type=QueryGroupType.TEAM_REVIEWER, name="Team Reviewer"),
    QueryGroupConfig(type=QueryGroupType.ASSIGNED, name="Assigned to Me"),
    QueryGroupConfig(type=QueryGroupType.MENTIONED, name="Mentioned/Involved"),
    QueryGroupConfig(type=QueryGroupType.LABEL, name="Labeled", enabled=False),
]
```

No config migration — treat all configs as fresh.

## Notes

- The `review_status` computed property on `PullRequest` will include team reviewers with `state="PENDING"` in its computation. This is correct — a pending team review request is still a pending review.
- Team-slug entries and user-login entries in `reviewer_map` are disjoint keys (a team slug like `"frontend"` will never collide with a user login), so there is no risk of one overwriting the other.

## Files Changed

| File | Changes |
|------|---------|
| `src/prdash/models.py` | Add `is_team` to `Reviewer`, update `_parse_reviewers()`, add `reclassify_review_groups()` |
| `src/prdash/config.py` | Add `ASSIGNED` to enum, update default group order |
| `src/prdash/github/queries.py` | Add `ASSIGNED` case to `build_search_query()` |
| `src/prdash/app.py` | Call `reclassify_review_groups()` between fetch and dedup |
| `tests/test_models.py` | Tests for `is_team` parsing, reclassification logic |
| `tests/test_config.py` | Update default group order assertions |
| `tests/test_github_client.py` | Tests for assigned query building |

## Acceptance Criteria

- [ ] PRs where only a team is requested appear in "Team Reviewer", not "Requested Reviewer"
- [ ] PRs where the user is individually requested appear in "Requested Reviewer"
- [ ] PRs where both the user and a team are requested appear in "Requested Reviewer" (highest priority)
- [ ] New "Assigned to Me" group shows PRs with `assignee:{username}`
- [ ] Default group order is: Ready to PR, My PRs, Requested Reviewer, Team Reviewer, Assigned to Me, Mentioned/Involved, Labeled
- [ ] Deduplication still works correctly with reclassified groups
- [ ] All existing tests pass (updated for new defaults)

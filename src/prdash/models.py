"""PR data models and GraphQL response parsers."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, computed_field


def _format_age(dt: datetime) -> str:
    """Human-readable age: '30m', '5h', '3d', '2w'."""
    delta = datetime.now(UTC) - dt
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 60:
        return f"{max(total_minutes, 1)}m"
    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"{total_hours}h"
    total_days = total_hours // 24
    if total_days < 7:
        return f"{total_days}d"
    return f"{total_days // 7}w"


class Reviewer(BaseModel, frozen=True):
    """A reviewer and their review state."""

    login: str
    state: str  # APPROVED, CHANGES_REQUESTED, PENDING, COMMENTED, DISMISSED
    is_team: bool = False


class CheckRun(BaseModel, frozen=True):
    """A CI check run result."""

    name: str
    status: str  # QUEUED, IN_PROGRESS, COMPLETED
    conclusion: str | None  # SUCCESS, FAILURE, NEUTRAL, etc.


class TimelineEvent(BaseModel, frozen=True):
    """A PR timeline event."""

    type: str  # IssueComment, PullRequestReview, HeadRefForcePushed
    author: str
    created_at: datetime
    body: str | None = None


_CI_PASS_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
_CI_FAIL_CONCLUSIONS = frozenset({
    "FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", "STARTUP_FAILURE",
})


class PullRequest(BaseModel, frozen=True):
    """A GitHub pull request with computed aggregate statuses."""

    id: str
    number: int
    title: str
    author: str
    url: str
    created_at: datetime
    repo_slug: str = ""
    is_draft: bool = False
    merge_state_status: str = "UNKNOWN"
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    reviewers: list[Reviewer] = Field(default_factory=list)
    checks: list[CheckRun] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    timeline_events: list[TimelineEvent] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ci_status(self) -> str:
        """Aggregate CI status: 'passing', 'failing', 'pending', 'none'."""
        if not self.checks:
            return "none"
        if any(c.conclusion in _CI_FAIL_CONCLUSIONS for c in self.checks):
            return "failing"
        if all(c.conclusion in _CI_PASS_CONCLUSIONS for c in self.checks):
            return "passing"
        return "pending"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ready_to_merge(self) -> bool:
        """Whether this PR is ready to merge (mergeStateStatus == CLEAN)."""
        return self.merge_state_status == "CLEAN"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def review_status(self) -> str:
        """Aggregate review status: 'approved', 'changes_requested', 'pending', 'none'."""
        if not self.reviewers:
            return "none"
        states = {r.state for r in self.reviewers}
        if "CHANGES_REQUESTED" in states:
            return "changes_requested"
        if "APPROVED" in states and "PENDING" not in states:
            return "approved"
        return "pending"

    def is_approved_by(self, username: str) -> bool:
        """Check if a specific user has approved this PR."""
        return any(r.login == username and r.state == "APPROVED" for r in self.reviewers)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age_display(self) -> str:
        """Human-readable age: '30m', '5h', '3d', '2w'."""
        return _format_age(self.created_at)


class BranchCommit(BaseModel, frozen=True):
    """A commit on a candidate branch."""

    sha: str
    short_sha: str
    message: str
    authored_date: datetime


class BranchFileChange(BaseModel, frozen=True):
    """A file changed on a candidate branch."""

    filename: str
    additions: int
    deletions: int
    status: str  # added, modified, removed, renamed


MAX_DISPLAY_COMMITS = 10
MAX_DISPLAY_FILES = 30


class CandidateBranch(BaseModel, frozen=True):
    """A branch that could become a PR."""

    name: str
    repo_slug: str
    last_commit_date: datetime
    compare_url: str
    default_branch: str = "main"
    commits: list[BranchCommit] = Field(default_factory=list)
    files: list[BranchFileChange] = Field(default_factory=list)
    total_commits: int = 0
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age_display(self) -> str:
        """Human-readable age of the last commit."""
        return _format_age(self.last_commit_date)


class QueryGroupResult(BaseModel):
    """PRs for a single query group (mutable for aggregation)."""

    group_name: str
    group_type: str
    pull_requests: list[PullRequest] = Field(default_factory=list)
    branches: list[CandidateBranch] = Field(default_factory=list)


def deduplicate_groups(groups: list[QueryGroupResult]) -> list[QueryGroupResult]:
    """Assign each PR to the highest-priority group (first in list order)."""
    seen: set[str] = set()
    deduped: list[QueryGroupResult] = []
    for group in groups:
        filtered = [pr for pr in group.pull_requests if pr.id not in seen]
        seen.update(pr.id for pr in filtered)
        deduped.append(QueryGroupResult(
            group_name=group.group_name,
            group_type=group.group_type,
            pull_requests=filtered,
            branches=group.branches,
        ))
    return deduped


def reclassify_review_groups(
    groups: list[QueryGroupResult], username: str
) -> list[QueryGroupResult]:
    """Move PRs from direct_reviewer to team_reviewer when user isn't individually requested."""
    from prdash.config import QueryGroupType

    direct_idx: int | None = None
    team_idx: int | None = None
    for i, g in enumerate(groups):
        if g.group_type == QueryGroupType.DIRECT_REVIEWER.value:
            direct_idx = i
        elif g.group_type == QueryGroupType.TEAM_REVIEWER.value:
            team_idx = i

    if direct_idx is None or team_idx is None:
        return groups

    direct_group = groups[direct_idx]
    team_group = groups[team_idx]

    keep_direct: list[PullRequest] = []
    move_to_team: list[PullRequest] = []

    for pr in direct_group.pull_requests:
        has_direct_request = any(
            r.login == username and not r.is_team for r in pr.reviewers
        )
        if has_direct_request:
            keep_direct.append(pr)
        else:
            move_to_team.append(pr)

    # Deduplicate moved PRs against existing team group PRs
    existing_team_ids = {pr.id for pr in team_group.pull_requests}
    new_team_prs = team_group.pull_requests + [
        pr for pr in move_to_team if pr.id not in existing_team_ids
    ]

    result = list(groups)
    result[direct_idx] = QueryGroupResult(
        group_name=direct_group.group_name,
        group_type=direct_group.group_type,
        pull_requests=keep_direct,
        branches=direct_group.branches,
    )
    result[team_idx] = QueryGroupResult(
        group_name=team_group.group_name,
        group_type=team_group.group_type,
        pull_requests=new_team_prs,
        branches=team_group.branches,
    )
    return result


# --- Response parsers ---


def _parse_reviewers(
    review_requests: list[dict], reviews: list[dict]
) -> list[Reviewer]:
    """Merge review requests (PENDING) with actual reviews, deduplicate by login."""
    # Maps login -> (state, is_team)
    reviewer_map: dict[str, tuple[str, bool]] = {}

    # Review requests are PENDING; distinguish User (login) vs Team (slug)
    for node in review_requests:
        requested = node.get("requestedReviewer") or {}
        user_login = requested.get("login")
        team_slug = requested.get("slug")
        if user_login:
            reviewer_map[user_login] = ("PENDING", False)
        elif team_slug:
            reviewer_map[team_slug] = ("PENDING", True)

    # Actual reviews override pending state; only users submit reviews (is_team=False).
    # Team slugs and user logins are disjoint keys, so this won't overwrite team entries.
    for node in reviews:
        author = node.get("author") or {}
        login = author.get("login")
        state = node.get("state")
        if login and state:
            reviewer_map[login] = (state, False)

    return [
        Reviewer(login=k, state=s, is_team=t) for k, (s, t) in reviewer_map.items()
    ]


def _parse_checks(commit_nodes: list[dict]) -> list[CheckRun]:
    """Parse CI checks from the last commit's statusCheckRollup."""
    if not commit_nodes:
        return []

    commit = commit_nodes[0].get("commit", {})
    rollup = commit.get("statusCheckRollup")
    if not rollup:
        return []

    contexts = rollup.get("contexts", {}).get("nodes", [])
    checks: list[CheckRun] = []
    for ctx in contexts:
        # CheckRun type
        if "name" in ctx:
            checks.append(
                CheckRun(
                    name=ctx["name"],
                    status=ctx.get("status", ""),
                    conclusion=ctx.get("conclusion"),
                )
            )
        # StatusContext type
        elif "context" in ctx:
            state = ctx.get("state", "")
            conclusion = None
            if state == "SUCCESS":
                conclusion = "SUCCESS"
            elif state in ("FAILURE", "ERROR"):
                conclusion = "FAILURE"
            checks.append(
                CheckRun(
                    name=ctx["context"],
                    status="COMPLETED" if conclusion else "IN_PROGRESS",
                    conclusion=conclusion,
                )
            )
    return checks


def _parse_timeline(timeline_nodes: list[dict]) -> list[TimelineEvent]:
    """Parse timeline events from GraphQL response."""
    events: list[TimelineEvent] = []
    for node in timeline_nodes:
        typename = node.get("__typename", "")

        if typename == "IssueComment":
            author = (node.get("author") or {}).get("login", "ghost")
            events.append(
                TimelineEvent(
                    type="IssueComment",
                    author=author,
                    created_at=node["createdAt"],
                    body=node.get("body"),
                )
            )
        elif typename == "PullRequestReview":
            author = (node.get("author") or {}).get("login", "ghost")
            events.append(
                TimelineEvent(
                    type="PullRequestReview",
                    author=author,
                    created_at=node["createdAt"],
                    body=node.get("body"),
                )
            )
        elif typename == "HeadRefForcePushedEvent":
            author = (node.get("actor") or {}).get("login", "ghost")
            events.append(
                TimelineEvent(
                    type="HeadRefForcePushed",
                    author=author,
                    created_at=node["createdAt"],
                )
            )
    return events


def parse_pr_node(node: dict) -> PullRequest:
    """Parse a single PR node from GraphQL search results."""
    author = (node.get("author") or {}).get("login", "ghost")
    labels = [n["name"] for n in (node.get("labels", {}) or {}).get("nodes", [])]
    review_requests = (node.get("reviewRequests", {}) or {}).get("nodes", [])
    reviews = (node.get("reviews", {}) or {}).get("nodes", [])
    commit_nodes = (node.get("commits", {}) or {}).get("nodes", [])
    timeline_nodes = (node.get("timelineItems", {}) or {}).get("nodes", [])

    repo_slug = (node.get("repository") or {}).get("nameWithOwner", "")

    return PullRequest(
        id=node["id"],
        number=node["number"],
        title=node["title"],
        author=author,
        url=node["url"],
        created_at=node["createdAt"],
        repo_slug=repo_slug,
        is_draft=node.get("isDraft", False),
        merge_state_status=node.get("mergeStateStatus", "UNKNOWN"),
        body=node.get("body"),
        additions=node.get("additions", 0),
        deletions=node.get("deletions", 0),
        labels=labels,
        reviewers=_parse_reviewers(review_requests, reviews),
        checks=_parse_checks(commit_nodes),
        timeline_events=_parse_timeline(timeline_nodes),
    )


def parse_search_results(
    data: dict,
) -> tuple[list[PullRequest], bool, str | None]:
    """Parse search results returning (PRs, has_next_page, end_cursor)."""
    search = data["data"]["search"]
    page_info = search["pageInfo"]
    nodes = search.get("nodes", [])

    prs = [parse_pr_node(node) for node in nodes if node]
    return prs, page_info["hasNextPage"], page_info.get("endCursor")


def parse_user_events(
    events: list[dict], repos: list[str]
) -> dict[str, set[str]]:
    """Parse REST user events into {repo_slug: {branch_names}}.

    Handles PushEvent (ref = "refs/heads/branch") and
    CreateEvent (ref_type = "branch", ref = "branch").
    Filters to configured repos if non-empty.
    """
    repo_set = set(repos) if repos else None
    result: dict[str, set[str]] = {}

    for event in events:
        event_type = event.get("type", "")
        repo_name = (event.get("repo") or {}).get("name", "")
        if not repo_name:
            continue
        if repo_set is not None and repo_name not in repo_set:
            continue

        if event_type == "PushEvent":
            ref = (event.get("payload") or {}).get("ref", "")
            if ref.startswith("refs/heads/"):
                branch = ref[len("refs/heads/"):]
                result.setdefault(repo_name, set()).add(branch)
        elif event_type == "CreateEvent":
            payload = event.get("payload") or {}
            if payload.get("ref_type") == "branch":
                branch = payload.get("ref", "")
                if branch:
                    result.setdefault(repo_name, set()).add(branch)

    return result


def parse_compare_response(
    data: dict,
) -> dict:
    """Parse a GitHub compare API response into branch enrichment fields.

    Returns a dict suitable for CandidateBranch.model_copy(update=...).
    """
    raw_commits = data.get("commits", [])
    raw_files = data.get("files", [])

    commits: list[BranchCommit] = []
    for c in raw_commits[:MAX_DISPLAY_COMMITS]:
        commit_data = c.get("commit", {})
        sha = c.get("sha", "")
        message = (commit_data.get("message") or "").split("\n", 1)[0]
        date_str = (commit_data.get("author") or {}).get("date", "")
        authored_date = (
            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_str
            else datetime.now(UTC)
        )
        commits.append(
            BranchCommit(
                sha=sha,
                short_sha=sha[:7],
                message=message,
                authored_date=authored_date,
            )
        )

    files: list[BranchFileChange] = []
    for f in raw_files[:MAX_DISPLAY_FILES]:
        files.append(
            BranchFileChange(
                filename=f.get("filename", ""),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                status=f.get("status", "modified"),
            )
        )

    total_additions = sum(f.get("additions", 0) for f in raw_files)
    total_deletions = sum(f.get("deletions", 0) for f in raw_files)

    return {
        "commits": commits,
        "files": files,
        "total_commits": len(raw_commits),
        "total_files": len(raw_files),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
    }


def parse_branch_verification(
    data: dict,
    alias_map: list[tuple[str, str, str, str]],
) -> list[CandidateBranch]:
    """Parse batched GraphQL branch verification response.

    Skips: null refs (deleted), branches with open PRs, branches older than
    7 days, and default branches.
    """
    gql_data = data.get("data", {})
    cutoff = datetime.now(UTC) - timedelta(days=7)
    branches: list[CandidateBranch] = []

    # Collect default branch names per repo alias
    default_branches: dict[str, str] = {}
    for repo_alias in {a[0] for a in alias_map}:
        repo_data = gql_data.get(repo_alias, {})
        default_ref = (repo_data.get("defaultBranchRef") or {})
        default_branches[repo_alias] = default_ref.get("name", "main")

    for repo_alias, branch_alias, repo_slug, branch_name in alias_map:
        repo_data = gql_data.get(repo_alias, {})
        ref_data = repo_data.get(branch_alias)

        # Null ref means branch was deleted
        if ref_data is None:
            continue

        # Skip default branch
        if branch_name == default_branches.get(repo_alias, "main"):
            continue

        # Skip branches with open PRs
        assoc = ref_data.get("associatedPullRequests", {})
        if assoc and assoc.get("totalCount", 0) > 0:
            continue

        # Parse commit date
        target = ref_data.get("target", {}) or {}
        committed_date_str = target.get("committedDate")
        if not committed_date_str:
            continue

        committed_date = datetime.fromisoformat(
            committed_date_str.replace("Z", "+00:00")
        )
        if committed_date < cutoff:
            continue

        owner, repo = repo_slug.split("/", 1)
        encoded = urllib.parse.quote(branch_name, safe="")
        compare_url = f"https://github.com/{owner}/{repo}/compare/{encoded}?expand=1"

        branches.append(
            CandidateBranch(
                name=branch_name,
                repo_slug=repo_slug,
                last_commit_date=committed_date,
                compare_url=compare_url,
                default_branch=default_branches.get(repo_alias, "main"),
            )
        )

    return branches

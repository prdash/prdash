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


class PullRequest(BaseModel, frozen=True):
    """A GitHub pull request with computed aggregate statuses."""

    id: str
    number: int
    title: str
    author: str
    url: str
    created_at: datetime
    repo_slug: str = ""
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    reviewers: list[Reviewer] = Field(default_factory=list)
    checks: list[CheckRun] = Field(default_factory=list)
    timeline_events: list[TimelineEvent] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ci_status(self) -> str:
        """Aggregate CI status: 'passing', 'failing', 'pending', 'none'."""
        if not self.checks:
            return "none"
        if any(c.conclusion == "FAILURE" for c in self.checks):
            return "failing"
        if all(c.conclusion == "SUCCESS" for c in self.checks):
            return "passing"
        return "pending"

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


class CandidateBranch(BaseModel, frozen=True):
    """A branch that could become a PR."""

    name: str
    repo_slug: str
    last_commit_date: datetime
    compare_url: str

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


# --- Response parsers ---


def _parse_reviewers(
    review_requests: list[dict], reviews: list[dict]
) -> list[Reviewer]:
    """Merge review requests (PENDING) with actual reviews, deduplicate by login."""
    reviewer_map: dict[str, str] = {}

    # Review requests are PENDING
    for node in review_requests:
        requested = node.get("requestedReviewer") or {}
        login = requested.get("login") or requested.get("slug")
        if login:
            reviewer_map[login] = "PENDING"

    # Actual reviews override pending state; keep latest per reviewer
    for node in reviews:
        author = node.get("author") or {}
        login = author.get("login")
        state = node.get("state")
        if login and state:
            reviewer_map[login] = state

    return [Reviewer(login=k, state=v) for k, v in reviewer_map.items()]


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
        body=node.get("body"),
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


def parse_refs_results(
    data: dict,
    username: str,
    owner: str,
    repo: str,
    default_branch: str,
) -> list[CandidateBranch]:
    """Parse branch refs and filter to candidate branches without open PRs."""
    repository = data.get("data", {}).get("repository", {})
    refs = repository.get("refs", {})
    nodes = refs.get("nodes", [])

    cutoff = datetime.now(UTC) - timedelta(days=7)
    branches: list[CandidateBranch] = []

    for node in nodes:
        name = node.get("name", "")
        if name == default_branch:
            continue

        # Skip branches with open PRs
        assoc = node.get("associatedPullRequests", {})
        if assoc and assoc.get("totalCount", 0) > 0:
            continue

        target = node.get("target", {}) or {}
        author_user = (target.get("author") or {}).get("user")
        if author_user is None:
            continue
        if author_user.get("login") != username:
            continue

        committed_date_str = target.get("committedDate")
        if not committed_date_str:
            continue

        committed_date = datetime.fromisoformat(committed_date_str.replace("Z", "+00:00"))
        if committed_date < cutoff:
            continue

        encoded = urllib.parse.quote(name, safe="")
        compare_url = f"https://github.com/{owner}/{repo}/compare/{encoded}?expand=1"

        branches.append(CandidateBranch(
            name=name,
            repo_slug=f"{owner}/{repo}",
            last_commit_date=committed_date,
            compare_url=compare_url,
        ))

    return branches

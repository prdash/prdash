"""GraphQL query template and search query builder."""

from __future__ import annotations

from prdash.config import AppConfig, QueryGroupConfig, QueryGroupType, get_org_from_repos

DEFAULT_PAGE_SIZE = 50

PR_SEARCH_QUERY = """\
query($searchQuery: String!, $first: Int!, $after: String) {
  search(query: $searchQuery, type: ISSUE, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        id
        number
        title
        url
        isDraft
        mergeStateStatus
        repository { nameWithOwner }
        createdAt
        body
        additions
        deletions
        author { login }
        labels(first: 20) { nodes { name } }
        reviewRequests(first: 20) {
          nodes {
            requestedReviewer {
              ... on User { login }
              ... on Team { slug }
            }
          }
        }
        reviews(last: 20) { nodes { author { login } state } }
        commits(last: 1) {
          nodes {
            commit {
              statusCheckRollup {
                contexts(first: 50) {
                  nodes {
                    __typename
                    ... on CheckRun { name status conclusion }
                    ... on StatusContext { context state }
                  }
                }
              }
            }
          }
        }
        timelineItems(
          last: 50
          itemTypes: [ISSUE_COMMENT, PULL_REQUEST_REVIEW, HEAD_REF_FORCE_PUSHED_EVENT]
        ) {
          nodes {
            __typename
            ... on IssueComment { author { login } createdAt body }
            ... on PullRequestReview { author { login } createdAt body state }
            ... on HeadRefForcePushedEvent { actor { login } createdAt }
          }
        }
      }
    }
  }
}
"""


def build_branch_verification_query(
    repo_branches: dict[str, list[str]],
) -> tuple[str, dict[str, str], list[tuple[str, str, str, str]]]:
    """Build a batched GraphQL query to verify specific branches across repos.

    Args:
        repo_branches: Mapping of {repo_slug: [branch_names]}.

    Returns:
        (query_str, variables_dict, alias_map) where alias_map is a list of
        (repo_alias, branch_alias, repo_slug, branch_name) tuples.
    """
    parts: list[str] = []
    variables: dict[str, str] = {}
    alias_map: list[tuple[str, str, str, str]] = []
    var_defs: list[str] = []

    for ri, (repo_slug, branches) in enumerate(repo_branches.items()):
        owner, name = repo_slug.split("/", 1)
        owner_var = f"owner{ri}"
        name_var = f"name{ri}"
        var_defs.append(f"${owner_var}: String!")
        var_defs.append(f"${name_var}: String!")
        variables[owner_var] = owner
        variables[name_var] = name

        repo_alias = f"r{ri}"
        branch_parts: list[str] = [f"defaultBranchRef {{ name }}"]
        for bi, branch in enumerate(branches):
            # Sanitize: skip branches with characters that could break the query
            if '"' in branch or "\\" in branch:
                continue
            branch_alias = f"b{ri}_{bi}"
            alias_map.append((repo_alias, branch_alias, repo_slug, branch))
            branch_parts.append(
                f'{branch_alias}: ref(qualifiedName: "refs/heads/{branch}") {{\n'
                f"  name\n"
                f"  target {{ ... on Commit {{ committedDate }} }}\n"
                f"  associatedPullRequests(states: OPEN, first: 1) {{ totalCount }}\n"
                f"}}"
            )

        parts.append(
            f"{repo_alias}: repository(owner: ${owner_var}, name: ${name_var}) {{\n"
            + "\n".join(branch_parts)
            + "\n}"
        )

    query = "query(" + ", ".join(var_defs) + ") {\n" + "\n".join(parts) + "\n}"
    return query, variables, alias_map


def build_search_query(config: AppConfig, group: QueryGroupConfig) -> list[str]:
    """Build GitHub search query strings for a query group.

    Returns a list because team_reviewer and label types produce one query
    per team slug or label respectively. Multiple repos also multiply queries.
    """
    if config.repos:
        prefixes = [f"repo:{r} is:pr is:open" for r in config.repos]
    else:
        prefixes = ["is:pr is:open"]

    match group.type:
        case QueryGroupType.DIRECT_REVIEWER:
            return [f"{p} review-requested:{config.username}" for p in prefixes]
        case QueryGroupType.TEAM_REVIEWER:
            if not config.repos:
                return []  # org unknown, can't form team-review-requested
            queries = []
            for r in config.repos:
                org = r.split("/")[0]
                for slug in config.team_slugs:
                    queries.append(f"repo:{r} is:pr is:open team-review-requested:{org}/{slug}")
            return queries
        case QueryGroupType.REVIEWED_BY:
            return [f"{p} reviewed-by:{config.username}" for p in prefixes]
        case QueryGroupType.MENTIONED:
            return [f"{p} involves:{config.username}" for p in prefixes]
        case QueryGroupType.AUTHORED:
            return [f"{p} author:{config.username}" for p in prefixes]
        case QueryGroupType.ASSIGNED:
            return [f"{p} assignee:{config.username}" for p in prefixes]
        case QueryGroupType.LABEL:
            return [f'{p} label:"{label}"' for p in prefixes for label in group.labels]
        case QueryGroupType.READY_TO_PR:
            return []

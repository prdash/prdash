"""GraphQL query template and search query builder."""

from __future__ import annotations

from gh_review_dashboard.config import AppConfig, QueryGroupConfig, QueryGroupType, get_org_from_repos

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
        repository { nameWithOwner }
        createdAt
        body
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
        case QueryGroupType.MENTIONED:
            return [f"{p} involves:{config.username}" for p in prefixes]
        case QueryGroupType.AUTHORED:
            return [f"{p} author:{config.username}" for p in prefixes]
        case QueryGroupType.LABEL:
            return [f'{p} label:"{label}"' for p in prefixes for label in group.labels]

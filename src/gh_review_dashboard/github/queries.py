"""GraphQL query template and search query builder."""

from __future__ import annotations

from gh_review_dashboard.config import AppConfig, QueryGroupConfig, QueryGroupType

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
    per team slug or label respectively.
    """
    prefix = f"repo:{config.repo.org}/{config.repo.name} is:pr is:open"

    match group.type:
        case QueryGroupType.DIRECT_REVIEWER:
            return [f"{prefix} review-requested:{config.username}"]
        case QueryGroupType.TEAM_REVIEWER:
            return [
                f"{prefix} team-review-requested:{config.repo.org}/{slug}"
                for slug in config.team_slugs
            ]
        case QueryGroupType.MENTIONED:
            return [f"{prefix} involves:{config.username}"]
        case QueryGroupType.AUTHORED:
            return [f"{prefix} author:{config.username}"]
        case QueryGroupType.LABEL:
            return [f'{prefix} label:"{label}"' for label in group.labels]

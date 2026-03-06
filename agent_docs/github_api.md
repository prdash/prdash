# GitHub API Reference

## Authentication

Extract token from the `gh` CLI (already installed and authenticated):
```python
import subprocess

def get_gh_token() -> str:
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()
```

Raise `AuthError` if `gh` is not installed, not authenticated, or returns empty token.

## httpx AsyncClient Setup

```python
import httpx

client = httpx.AsyncClient(
    base_url="https://api.github.com",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    },
    timeout=httpx.Timeout(30.0),
)
```

- Create client once, reuse across queries
- Close with `await client.aclose()` on app shutdown
- Pass client via dependency injection (constructor arg)

## GraphQL Endpoint

POST to `/graphql` with JSON body:
```python
response = await client.post("/graphql", json={"query": query, "variables": variables})
data = response.json()
if "errors" in data:
    raise GitHubAPIError(data["errors"])
```

## Query Structure

Each query group uses GitHub's `search` API with qualifiers:

| Group Type | Search Qualifier |
|---|---|
| Direct reviewer | `review-requested:{username}` |
| Team reviewer | `team-review-requested:{org}/{team}` |
| Mentioned/Involved | `involves:{username}` |
| Authored | `author:{username}` |
| Label-based | `label:{label}` |

Common qualifiers added to all: `repo:{org}/{repo} is:pr is:open`

Example query:
```graphql
query($searchQuery: String!, $first: Int!, $after: String) {
  search(query: $searchQuery, type: ISSUE, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title url createdAt
        author { login }
        labels(first: 10) { nodes { name color } }
        reviewRequests(first: 10) { nodes { requestedReviewer { ... on User { login } ... on Team { name slug } } } }
        reviews(last: 20) { nodes { author { login } state submittedAt } }
        commits(last: 1) { nodes { commit { statusCheckRollup { state contexts(first: 20) { nodes { ... on CheckRun { name conclusion status } } } } } } }
        timelineItems(last: 30, itemTypes: [PULL_REQUEST_REVIEW, ISSUE_COMMENT, HEAD_REF_FORCE_PUSHED_EVENT, MERGED_EVENT]) {
          nodes { __typename ... }
        }
      }
    }
  }
}
```

## Response Parsing

- Navigate: `data["data"]["search"]["nodes"]` — each node is a PR
- Handle nulls: author can be null (ghost users), check rollup can be null
- Deduplicate reviews: same reviewer may have multiple reviews; use latest per reviewer
- Map GraphQL fields to Pydantic `PullRequest` model

## Error Handling

| Error | Detection | Action |
|---|---|---|
| HTTP 401 | `response.status_code == 401` | Raise `AuthError` — token expired or invalid |
| HTTP 403 | `response.status_code == 403` | Rate limit or scope issue; check `X-RateLimit-Remaining` |
| GraphQL errors | `"errors" in response_json` | Raise `GitHubAPIError` with error messages |
| Network error | `httpx.RequestError` | Raise `GitHubAPIError`; app shows "offline" state |
| Timeout | `httpx.TimeoutException` | Raise `GitHubAPIError`; retry on next refresh cycle |

## Pagination

```python
has_next = True
cursor = None
all_prs = []
while has_next:
    variables = {"searchQuery": query, "first": 50, "after": cursor}
    data = await self._execute_query(graphql_query, variables)
    search = data["data"]["search"]
    all_prs.extend(parse_pr_nodes(search["nodes"]))
    has_next = search["pageInfo"]["hasNextPage"]
    cursor = search["pageInfo"]["endCursor"]
```

## Parallel Queries

Fetch all query groups simultaneously:
```python
import asyncio

async def fetch_all_groups(groups: list[QueryGroup]) -> dict[str, list[PullRequest]]:
    results = await asyncio.gather(
        *(self.fetch_prs(group) for group in groups),
        return_exceptions=True,
    )
    # Handle individual group failures gracefully
    return {g.name: r for g, r in zip(groups, results) if not isinstance(r, Exception)}
```

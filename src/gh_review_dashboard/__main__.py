import sys

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.auth import get_github_token
from gh_review_dashboard.config import load_config
from gh_review_dashboard.exceptions import DashboardError
from gh_review_dashboard.github.client import GitHubClient, create_http_client


def main():
    try:
        config = load_config()
        token = get_github_token()
    except DashboardError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    http_client = create_http_client(token)
    github_client = GitHubClient(http_client)
    app = ReviewDashboardApp(config=config, github_client=github_client)
    app.run()


if __name__ == "__main__":
    main()

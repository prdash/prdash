import argparse
import sys

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.auth import get_github_token
from gh_review_dashboard.config import CONFIG_FILE, load_config
from gh_review_dashboard.exceptions import DashboardError
from gh_review_dashboard.github.client import GitHubClient, create_http_client
from gh_review_dashboard.screens.setup_wizard import SetupWizardApp
from gh_review_dashboard.updater import get_version, run_upgrade


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghrd",
        description="GitHub Review Dashboard",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update gh-review-dashboard to the latest version",
    )
    return parser


def main():
    args = _build_parser().parse_args()

    if args.update:
        run_upgrade()
        return

    try:
        token = get_github_token()
    except DashboardError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not CONFIG_FILE.exists():
        wizard = SetupWizardApp(token=token)
        wizard.run()
        if not wizard.wizard_state.completed:
            sys.exit(0)

    try:
        config = load_config()
    except DashboardError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    http_client = create_http_client(token, timeout=config.timeout)
    github_client = GitHubClient(http_client)
    app = ReviewDashboardApp(config=config, github_client=github_client)
    app.run()


if __name__ == "__main__":
    main()

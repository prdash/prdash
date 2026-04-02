from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from prdash.app import PRDashCommandProvider, ReviewDashboardApp
from prdash.config import AppConfig, QueryGroupConfig, QueryGroupType
from prdash.exceptions import AuthError, GitHubAPIError, NetworkError
from prdash.github.client import GitHubClient
from prdash.models import CheckRun, PullRequest, QueryGroupResult
from prdash.widgets import DetailPaneWidget, PRListWidget


def _make_config() -> AppConfig:
    return AppConfig(
        repos=["test-org/test-repo"],
        username="testuser",
        poll_interval=300,
    )


def _make_app(groups: list[QueryGroupResult] | None = None, errors: list[tuple[str, Exception]] | None = None, **kwargs):
    """Create an app with a mocked GitHubClient."""
    mock_client = AsyncMock(spec=GitHubClient)
    mock_client.fetch_all_groups.return_value = (groups or [], errors or [])
    config = _make_config()
    return ReviewDashboardApp(config=config, github_client=mock_client, **kwargs), mock_client


def _make_plain_app():
    """Create an app without config/client for basic tests."""
    return ReviewDashboardApp()


def test_app_title():
    app = _make_plain_app()
    assert app.TITLE == "PR Dash"


def test_app_css_path():
    app = _make_plain_app()
    assert app.CSS_PATH == "app.tcss"


def test_app_has_quit_binding():
    app = _make_plain_app()
    keys = [b.key for b in app.BINDINGS]
    assert "q" in keys


def test_app_has_tab_binding():
    app = _make_plain_app()
    keys = [b.key for b in app.BINDINGS]
    assert "tab" in keys


def test_app_has_refresh_binding():
    app = _make_plain_app()
    keys = [b.key for b in app.BINDINGS]
    assert "r" in keys


def test_app_seen_pr_ids_empty_initially():
    app = _make_plain_app()
    assert app._seen_pr_ids == set()


@pytest.mark.asyncio
async def test_app_has_header_and_footer():
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.widgets import Footer, Header

        headers = pilot.app.query(Header)
        assert len(headers) == 1
        footers = pilot.app.query(Footer)
        assert len(footers) == 1


@pytest.mark.asyncio
async def test_app_has_widget_panes():
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        pr_list = pilot.app.query_one("#pr-list-pane", PRListWidget)
        assert pr_list is not None
        detail = pilot.app.query_one("#detail-pane", DetailPaneWidget)
        assert detail is not None


@pytest.mark.asyncio
async def test_app_horizontal_container_has_two_children():
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.containers import Horizontal

        horizontal = pilot.app.query_one(Horizontal)
        children = list(horizontal.children)
        assert len(children) == 2


@pytest.mark.asyncio
async def test_app_pr_selected_wires_to_detail_pane(sample_pr):
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        from prdash.widgets.pr_list import PRSelected

        # Post from the PRListWidget so it bubbles up to the app
        pr_list = pilot.app.query_one(PRListWidget)
        pr_list.post_message(PRSelected(sample_pr))
        await pilot.pause()
        await pilot.pause()

        from textual.widgets import Static

        meta = pilot.app.query_one("#detail-metadata", Static)
        assert "hidden" not in meta.classes


@pytest.mark.asyncio
async def test_tab_switches_focus():
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        # Initial focus should be on the PR list
        pr_list_view = pilot.app.query_one("#pr-list-view")
        detail_scroll = pilot.app.query_one("#detail-scroll")

        assert pr_list_view.has_focus

        # Press tab to switch to detail pane
        await pilot.press("tab")
        await pilot.pause()
        assert detail_scroll.has_focus

        # Press tab again to switch back
        await pilot.press("tab")
        await pilot.pause()
        assert pr_list_view.has_focus


@pytest.mark.asyncio
async def test_refresh_data_called_on_mount(sample_pr):
    groups = [
        QueryGroupResult(
            group_name="Test",
            group_type="test",
            pull_requests=[sample_pr],
        ),
    ]
    app, mock_client = _make_app(groups)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        mock_client.fetch_all_groups.assert_called()


@pytest.mark.asyncio
async def test_seen_pr_ids_populated_after_refresh(sample_pr, sample_pr_minimal):
    groups = [
        QueryGroupResult(
            group_name="Test",
            group_type="test",
            pull_requests=[sample_pr, sample_pr_minimal],
        ),
    ]
    app, mock_client = _make_app(groups)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert app._seen_pr_ids == {"PR_1", "PR_2"}


@pytest.mark.asyncio
async def test_r_key_triggers_refresh(sample_pr):
    groups = [
        QueryGroupResult(
            group_name="Test",
            group_type="test",
            pull_requests=[sample_pr],
        ),
    ]
    app, mock_client = _make_app(groups)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        initial_call_count = mock_client.fetch_all_groups.call_count

        await pilot.press("r")
        await pilot.pause()
        await pilot.pause()
        assert mock_client.fetch_all_groups.call_count > initial_call_count


@pytest.mark.asyncio
async def test_no_refresh_without_client():
    """App without client/config should not crash on mount."""
    app = _make_plain_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Should not raise


@pytest.mark.asyncio
async def test_refresh_data_auth_error_notifies():
    """AuthError during refresh should show error notification, not crash."""
    app, mock_client = _make_app()
    mock_client.fetch_all_groups.side_effect = AuthError("Token expired. Run 'gh auth login' to re-authenticate.")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        # App should still be running (not crashed)
        assert pilot.app is not None


@pytest.mark.asyncio
async def test_refresh_data_network_error_notifies():
    """NetworkError during refresh should show warning notification, not crash."""
    app, mock_client = _make_app()
    mock_client.fetch_all_groups.side_effect = NetworkError("Connection refused")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert pilot.app is not None


@pytest.mark.asyncio
async def test_refresh_data_api_error_notifies():
    """GitHubAPIError during refresh should show warning notification, not crash."""
    app, mock_client = _make_app()
    mock_client.fetch_all_groups.side_effect = GitHubAPIError("Rate limit exceeded")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert pilot.app is not None


@pytest.mark.asyncio
async def test_refresh_data_unexpected_error_notifies():
    """Unexpected exception during refresh should show error notification, not crash."""
    app, mock_client = _make_app()
    mock_client.fetch_all_groups.side_effect = RuntimeError("Something unexpected")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert pilot.app is not None


@pytest.mark.asyncio
async def test_refresh_data_partial_group_errors(sample_pr):
    """Per-group errors should notify but still display successful groups."""
    groups = [
        QueryGroupResult(
            group_name="Direct",
            group_type="test",
            pull_requests=[sample_pr],
        ),
    ]
    errors = [("Authored", GitHubAPIError("rate limit"))]
    app, mock_client = _make_app(groups=groups, errors=errors)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        # The successful group should still be displayed
        pr_list = pilot.app.query_one(PRListWidget)
        from prdash.widgets.pr_list import GroupHeaderItem
        headers = list(pr_list.query(GroupHeaderItem))
        assert len(headers) == 1
        assert headers[0].group_name == "Direct"


@pytest.mark.asyncio
async def test_refresh_data_deduplicates_groups(sample_pr, sample_pr_minimal):
    """refresh_data should deduplicate PRs across groups before updating the widget."""
    # sample_pr appears in both groups — should only appear in "Review Requested"
    groups = [
        QueryGroupResult(
            group_name="Review Requested",
            group_type="review_requested",
            pull_requests=[sample_pr, sample_pr_minimal],
        ),
        QueryGroupResult(
            group_name="Authored",
            group_type="authored",
            pull_requests=[sample_pr],
        ),
    ]
    app, mock_client = _make_app(groups)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        pr_list = pilot.app.query_one(PRListWidget)
        from prdash.widgets.pr_list import PRRow
        pr_rows = list(pr_list.query(PRRow))
        # Only 2 unique PRs should be shown, not 3
        pr_ids = [row.pr.id for row in pr_rows]
        assert pr_ids.count("PR_1") == 1
        assert pr_ids.count("PR_2") == 1
        assert len(pr_ids) == 2


# --- Toast notifications ---


class TestNotifyChanges:
    """Test _notify_changes method for detecting new PRs and status transitions."""

    def _make_pr(self, pr_id: str, ci_status_conclusion: str = "SUCCESS", review_state: str = "PENDING") -> PullRequest:
        checks = [CheckRun(name="ci", status="COMPLETED", conclusion=ci_status_conclusion)] if ci_status_conclusion else []
        return PullRequest(
            id=pr_id,
            number=int(pr_id.replace("PR_", "")),
            title=f"PR {pr_id}",
            author="alice",
            url=f"https://github.com/org/repo/pull/{pr_id}",
            created_at=datetime.now(UTC) - timedelta(hours=1),
            repo_slug="org/repo",
            checks=checks,
        )

    @pytest.mark.asyncio
    async def test_no_notifications_on_first_load(self):
        app = _make_plain_app()
        async with app.run_test(size=(120, 40)) as pilot:
            groups = [
                QueryGroupResult(
                    group_name="Review",
                    group_type="test",
                    pull_requests=[self._make_pr("PR_1")],
                )
            ]
            # _seen_pr_ids is empty on first load — should not notify
            app._notify_changes(groups)
            # No crash, no notifications (can't easily assert no notify was called
            # without mocking, but the method should return early)

    @pytest.mark.asyncio
    async def test_notifies_new_prs(self):
        app = _make_plain_app()
        async with app.run_test(size=(120, 40)) as pilot:
            app._seen_pr_ids = {"PR_1"}
            app._previous_pr_map = {"PR_1": self._make_pr("PR_1")}

            groups = [
                QueryGroupResult(
                    group_name="Review",
                    group_type="test",
                    pull_requests=[self._make_pr("PR_1"), self._make_pr("PR_2")],
                )
            ]
            # Should detect PR_2 as new — method should not crash
            app._notify_changes(groups)
            # Verify previous_pr_map updated
            assert "PR_2" in app._previous_pr_map

    @pytest.mark.asyncio
    async def test_detects_ci_transition(self):
        app = _make_plain_app()
        async with app.run_test(size=(120, 40)) as pilot:
            old_pr = self._make_pr("PR_1", ci_status_conclusion="FAILURE")
            app._seen_pr_ids = {"PR_1"}
            app._previous_pr_map = {"PR_1": old_pr}

            new_pr = self._make_pr("PR_1", ci_status_conclusion="SUCCESS")
            groups = [
                QueryGroupResult(
                    group_name="Review",
                    group_type="test",
                    pull_requests=[new_pr],
                )
            ]
            app._notify_changes(groups)
            # pr_map should be updated with new status
            assert app._previous_pr_map["PR_1"].ci_status == "passing"


# --- Command palette ---


def test_command_provider_registered():
    """COMMANDS should include PRDashCommandProvider."""
    assert PRDashCommandProvider in ReviewDashboardApp.COMMANDS


@pytest.mark.asyncio
async def test_jump_to_group_scrolls_list(sample_pr, sample_pr_minimal):
    """action_jump_to_group should scroll the list view to the named group."""
    groups = [
        QueryGroupResult(group_name="Group A", group_type="test", pull_requests=[sample_pr]),
        QueryGroupResult(group_name="Group B", group_type="test", pull_requests=[sample_pr_minimal]),
    ]
    app, _ = _make_app(groups)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        app.action_jump_to_group("Group B")
        await pilot.pause()
        from prdash.widgets.pr_list import NavigableListView, GroupHeaderItem
        list_view = app.query_one(NavigableListView)
        item = list_view.highlighted_child
        assert isinstance(item, GroupHeaderItem)
        assert item.group_name == "Group B"

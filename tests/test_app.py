from unittest.mock import AsyncMock, patch

import pytest

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.config import AppConfig, QueryGroupConfig, QueryGroupType, RepoConfig
from gh_review_dashboard.github.client import GitHubClient
from gh_review_dashboard.models import QueryGroupResult
from gh_review_dashboard.widgets import DetailPaneWidget, PRListWidget


def _make_config() -> AppConfig:
    return AppConfig(
        repo=RepoConfig(org="test-org", name="test-repo"),
        username="testuser",
        poll_interval=300,
    )


def _make_app(groups: list[QueryGroupResult] | None = None, **kwargs):
    """Create an app with a mocked GitHubClient."""
    mock_client = AsyncMock(spec=GitHubClient)
    mock_client.fetch_all_groups.return_value = groups or []
    config = _make_config()
    return ReviewDashboardApp(config=config, github_client=mock_client, **kwargs), mock_client


def _make_plain_app():
    """Create an app without config/client for basic tests."""
    return ReviewDashboardApp()


def test_app_title():
    app = _make_plain_app()
    assert app.TITLE == "GitHub Review Dashboard"


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
        from gh_review_dashboard.widgets.pr_list import PRSelected

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

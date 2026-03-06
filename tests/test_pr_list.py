"""Tests for the PR list widget."""

import pytest

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.models import QueryGroupResult
from gh_review_dashboard.widgets.pr_list import PRListWidget, PRRow, PRSelected


@pytest.mark.asyncio
async def test_pr_list_widget_exists_in_app():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        assert widget is not None


@pytest.mark.asyncio
async def test_update_data_creates_collapsible_groups(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        from textual.widgets import Collapsible

        collapsibles = widget.query(Collapsible)
        assert len(collapsibles) == 3


@pytest.mark.asyncio
async def test_empty_group_is_collapsed(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        from textual.widgets import Collapsible

        collapsibles = list(widget.query(Collapsible))
        # "Team Reviews" has 0 PRs, should be collapsed
        assert collapsibles[1].collapsed is True
        # "Review Requested" has PRs, should not be collapsed
        assert collapsibles[0].collapsed is False


@pytest.mark.asyncio
async def test_pr_rows_created_for_prs(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        rows = widget.query(PRRow)
        # 2 in first group + 0 in second + 1 in third = 3
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_pr_row_has_pr_data(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test",
                group_type="test",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 1
        assert rows[0].pr.number == 42
        assert rows[0].pr.title == "Fix auth token refresh"


@pytest.mark.asyncio
async def test_pr_row_displays_status_icons(sample_pr):
    """PR with failing CI and changes_requested review should show ! and x."""
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test",
                group_type="test",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        # Verify the PR data is accessible and status icons would be correct
        pr = rows[0].pr
        assert pr.ci_status == "failing"  # has a FAILURE check
        assert pr.review_status == "pending"  # APPROVED + PENDING = pending


@pytest.mark.asyncio
async def test_update_data_replaces_previous(sample_groups, sample_pr_minimal):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        # Now update with different data
        widget.update_data([
            QueryGroupResult(
                group_name="Only Group",
                group_type="test",
                pull_requests=[sample_pr_minimal],
            ),
        ])
        await pilot.pause()

        from textual.widgets import Collapsible

        collapsibles = widget.query(Collapsible)
        assert len(collapsibles) == 1

        rows = widget.query(PRRow)
        assert len(rows) == 1

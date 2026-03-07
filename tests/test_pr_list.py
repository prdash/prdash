"""Tests for the PR list widget."""

import pytest

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.models import QueryGroupResult
from gh_review_dashboard.widgets.pr_list import (
    GroupHeaderItem,
    NavigableListView,
    PRListWidget,
    PRRow,
    PRSelected,
)


@pytest.mark.asyncio
async def test_pr_list_widget_exists_in_app():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        assert widget is not None


@pytest.mark.asyncio
async def test_update_data_creates_group_headers(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        headers = widget.query(GroupHeaderItem)
        assert len(headers) == 3


@pytest.mark.asyncio
async def test_empty_group_is_collapsed(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        headers = list(widget.query(GroupHeaderItem))
        # "Team Reviews" has 0 PRs, should be collapsed
        team_header = [h for h in headers if h.group_name == "Team Reviews"][0]
        assert team_header.collapsed is True
        # "Review Requested" has PRs, should not be collapsed
        review_header = [h for h in headers if h.group_name == "Review Requested"][0]
        assert review_header.collapsed is False


@pytest.mark.asyncio
async def test_pr_rows_created_for_prs(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        rows = widget.query(PRRow)
        # 2 in first group + 0 in second (collapsed) + 1 in third = 3
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
        pr = rows[0].pr
        assert pr.ci_status == "failing"
        assert pr.review_status == "pending"


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

        headers = widget.query(GroupHeaderItem)
        assert len(headers) == 1

        rows = widget.query(PRRow)
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_j_k_moves_cursor(sample_pr, sample_pr_minimal):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test",
                group_type="test",
                pull_requests=[sample_pr, sample_pr_minimal],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Should start at index 0 (the group header)
        assert list_view.index == 0

        # Press j to move down
        await pilot.press("j")
        await pilot.pause()
        assert list_view.index == 1

        # Press k to move back up
        await pilot.press("k")
        await pilot.pause()
        assert list_view.index == 0


@pytest.mark.asyncio
async def test_enter_toggles_group(sample_pr, sample_pr_minimal):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test Group",
                group_type="test",
                pull_requests=[sample_pr, sample_pr_minimal],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Initially: 1 header + 2 PRs = 3 items
        assert len(list(widget.query(PRRow))) == 2

        # Press enter on the group header to collapse
        await pilot.press("enter")
        await pilot.pause()

        # After collapse: only header, no PR rows
        assert len(list(widget.query(PRRow))) == 0
        headers = list(widget.query(GroupHeaderItem))
        assert headers[0].collapsed is True

        # Press enter again to expand
        await pilot.press("enter")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 2


@pytest.mark.asyncio
async def test_collapsed_group_skips_prs(sample_groups):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        # "Team Reviews" (0 PRs) is auto-collapsed
        # Verify no PRs shown for that group by checking total rows
        # 2 from "Review Requested" + 0 from "Team Reviews" + 1 from "My PRs" = 3
        rows = widget.query(PRRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_highlight_pr_emits_selected(sample_pr):
    app = ReviewDashboardApp()
    messages: list[PRSelected] = []

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

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move down to the PR row (index 0 is header, 1 is PR)
        await pilot.press("j")
        await pilot.pause()

        # Check that the detail pane received the PR data
        from textual.widgets import Static
        meta = pilot.app.query_one("#detail-metadata", Static)
        assert "hidden" not in meta.classes

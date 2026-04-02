"""Tests for the PR list widget."""

from unittest.mock import AsyncMock, patch

import pytest

from prdash.app import ReviewDashboardApp
from prdash.models import CandidateBranch, PullRequest, QueryGroupResult, Reviewer
from prdash.widgets.pr_list import (
    BranchRow,
    BranchSelected,
    EmptyGroupItem,
    GroupHeaderItem,
    NavigableListView,
    PRListWidget,
    PRRow,
    PRSelected,
)


def _make_app():
    return ReviewDashboardApp()


@pytest.mark.asyncio
async def test_pr_list_widget_exists_in_app():
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        assert widget is not None


@pytest.mark.asyncio
async def test_update_data_creates_group_headers(sample_groups):
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        headers = widget.query(GroupHeaderItem)
        assert len(headers) == 3


@pytest.mark.asyncio
async def test_empty_group_is_collapsed(sample_groups):
    app = _make_app()
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
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(sample_groups)
        await pilot.pause()

        rows = widget.query(PRRow)
        # 2 in first group + 0 in second (collapsed) + 1 in third = 3
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_pr_row_has_pr_data(sample_pr):
    app = _make_app()
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
    app = _make_app()
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
    app = _make_app()
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
    app = _make_app()
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
    app = _make_app()
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
    app = _make_app()
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
    app = _make_app()
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


@pytest.mark.asyncio
async def test_enter_on_pr_row_opens_browser(sample_pr):
    """Pressing Enter on a PR row should open the PR URL in the browser."""
    app = _make_app()
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

        # Move to the PR row (index 0 is header, 1 is PR)
        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.webbrowser.open") as mock_open:
            await pilot.press("enter")
            await pilot.pause()
            mock_open.assert_called_once_with(sample_pr.url)


# --- Readability improvement tests (T25) ---


@pytest.mark.asyncio
async def test_pr_row_renders_ci_label(sample_pr):
    """PR with failing CI should show CI:fail in content."""
    app = _make_app()
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
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "CI:fail" in str(label_static.content)


@pytest.mark.asyncio
async def test_pr_row_renders_review_label(sample_pr):
    """PR with pending review should show Rev:pend in content."""
    app = _make_app()
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
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "Rev:pend" in str(label_static.content)


@pytest.mark.asyncio
async def test_pr_row_is_multiline(sample_pr):
    """PR row should render as two lines with title and @author."""
    app = _make_app()
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
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        content = str(label_static.content)
        assert "\n" in content
        assert sample_pr.title in content
        assert f"@{sample_pr.author}" in content


@pytest.mark.asyncio
async def test_group_header_uses_triangle_arrows(sample_pr):
    """Expanded group header should show ▼ triangle arrow."""
    app = _make_app()
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

        headers = list(widget.query(GroupHeaderItem))
        from textual.widgets import Static
        label = headers[0].query_one(Static)
        assert "▼" in str(label.content)


# --- New-item indicator tests ---


@pytest.mark.asyncio
async def test_update_data_no_seen_ids_no_new_markers(sample_pr):
    """On first load (seen_ids=None), no PRs should be marked new."""
    app = _make_app()
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
        assert rows[0].is_new is False


@pytest.mark.asyncio
async def test_update_data_empty_seen_ids_no_new_markers(sample_pr):
    """On first load (seen_ids=set()), no PRs should be marked new."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [
                QueryGroupResult(
                    group_name="Test",
                    group_type="test",
                    pull_requests=[sample_pr],
                ),
            ],
            seen_ids=set(),
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 1
        assert rows[0].is_new is False


@pytest.mark.asyncio
async def test_update_data_with_seen_ids_marks_new_prs(sample_pr, sample_pr_minimal):
    """PRs not in seen_ids should be marked as new."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        # PR_1 was seen before, PR_2 is new
        widget.update_data(
            [
                QueryGroupResult(
                    group_name="Test",
                    group_type="test",
                    pull_requests=[sample_pr, sample_pr_minimal],
                ),
            ],
            seen_ids={"PR_1"},
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 2
        pr1_row = [r for r in rows if r.pr.id == "PR_1"][0]
        pr2_row = [r for r in rows if r.pr.id == "PR_2"][0]
        assert pr1_row.is_new is False
        assert pr2_row.is_new is True


@pytest.mark.asyncio
async def test_new_pr_row_renders_marker(sample_pr):
    """A new PR row should render the ● marker."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        # Pass seen_ids that don't include this PR
        widget.update_data(
            [
                QueryGroupResult(
                    group_name="Test",
                    group_type="test",
                    pull_requests=[sample_pr],
                ),
            ],
            seen_ids={"OTHER_PR"},
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].is_new is True
        # Check the Static has the pr-row-new class
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-new" in label_static.classes
        marker_static = rows[0].query_one(".pr-row-marker", Static)
        assert "●" in str(marker_static.content)


@pytest.mark.asyncio
async def test_seen_pr_row_no_marker(sample_pr):
    """A seen PR row should not render the ● marker."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [
                QueryGroupResult(
                    group_name="Test",
                    group_type="test",
                    pull_requests=[sample_pr],
                ),
            ],
            seen_ids={"PR_1"},
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].is_new is False
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-new" not in label_static.classes
        marker_static = rows[0].query_one(".pr-row-marker", Static)
        assert "●" not in str(marker_static.content)


# --- Empty group placeholder tests ---


@pytest.mark.asyncio
async def test_expanded_empty_group_shows_placeholder():
    """An expanded group with 0 PRs should show an EmptyGroupItem placeholder."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Empty Group",
                group_type="test",
                pull_requests=[],
            ),
        ])
        await pilot.pause()

        # The group starts collapsed (auto-collapse for empty groups).
        # Expand it by toggling.
        widget._header_states["Empty Group"] = False
        widget._rebuild_list()
        await pilot.pause()

        placeholders = list(widget.query(EmptyGroupItem))
        assert len(placeholders) == 1
        from textual.widgets import Static
        label = placeholders[0].query_one(Static)
        assert "No pull requests found" in str(label.content)


@pytest.mark.asyncio
async def test_enter_on_empty_group_item_is_noop(sample_pr):
    """Pressing Enter on an EmptyGroupItem should not crash or open browser."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Empty Group",
                group_type="test",
                pull_requests=[],
            ),
        ])
        await pilot.pause()

        # Expand the empty group
        widget._header_states["Empty Group"] = False
        widget._rebuild_list()
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move to the EmptyGroupItem (index 0=header, 1=empty placeholder)
        await pilot.press("j")
        await pilot.pause()

        # Press enter — should not crash
        with patch("prdash.widgets.pr_list.webbrowser.open") as mock_open:
            await pilot.press("enter")
            await pilot.pause()
            mock_open.assert_not_called()


# --- "Approved by me" tests (T26) ---


def _make_pr_with_reviewers(pr_id: str, number: int, title: str, reviewers: list[Reviewer]) -> PullRequest:
    from datetime import UTC, datetime, timedelta
    return PullRequest(
        id=pr_id,
        number=number,
        title=title,
        author="alice",
        url=f"https://github.com/org/repo/pull/{number}",
        created_at=datetime.now(UTC) - timedelta(hours=1),
        reviewers=reviewers,
    )


@pytest.mark.asyncio
async def test_approved_prs_sort_to_bottom_in_reviewer_groups():
    """PRs approved by the user should sort to the bottom of reviewer groups."""
    approved_pr = _make_pr_with_reviewers("PR_A", 1, "Approved PR", [Reviewer(login="me", state="APPROVED")])
    pending_pr = _make_pr_with_reviewers("PR_B", 2, "Pending PR", [Reviewer(login="me", state="PENDING")])
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [QueryGroupResult(group_name="Review Requested", group_type="review_requested", pull_requests=[approved_pr, pending_pr])],
            username="me",
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 2
        assert rows[0].pr.id == "PR_B"  # pending first
        assert rows[1].pr.id == "PR_A"  # approved last


@pytest.mark.asyncio
async def test_authored_group_preserves_api_order():
    """Authored group should not sort by approved status."""
    approved_pr = _make_pr_with_reviewers("PR_A", 1, "Approved PR", [Reviewer(login="me", state="APPROVED")])
    pending_pr = _make_pr_with_reviewers("PR_B", 2, "Pending PR", [Reviewer(login="me", state="PENDING")])
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [QueryGroupResult(group_name="My PRs", group_type="authored", pull_requests=[approved_pr, pending_pr])],
            username="me",
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 2
        assert rows[0].pr.id == "PR_A"  # original order preserved
        assert rows[1].pr.id == "PR_B"


@pytest.mark.asyncio
async def test_approved_row_gets_css_class():
    """Approved PR row in a reviewer group should get pr-row-approved class."""
    approved_pr = _make_pr_with_reviewers("PR_A", 1, "Approved PR", [Reviewer(login="me", state="APPROVED")])
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [QueryGroupResult(group_name="Review Requested", group_type="review_requested", pull_requests=[approved_pr])],
            username="me",
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].approved_by_me is True
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-approved" in label.classes


@pytest.mark.asyncio
async def test_authored_group_rows_no_approved_class():
    """Authored group rows should never get pr-row-approved class."""
    approved_pr = _make_pr_with_reviewers("PR_A", 1, "Approved PR", [Reviewer(login="me", state="APPROVED")])
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [QueryGroupResult(group_name="My PRs", group_type="authored", pull_requests=[approved_pr])],
            username="me",
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].approved_by_me is False
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-approved" not in label.classes


# --- Arrow key collapse/expand tests (T29) ---


@pytest.mark.asyncio
async def test_right_arrow_expands_collapsed_group(sample_pr, sample_pr_minimal):
    """Right arrow on a collapsed group header should expand it."""
    app = _make_app()
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

        # Collapse via enter first
        await pilot.press("enter")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 0

        # Expand via right arrow
        await pilot.press("right")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 2


@pytest.mark.asyncio
async def test_left_arrow_collapses_expanded_group(sample_pr, sample_pr_minimal):
    """Left arrow on an expanded group header should collapse it."""
    app = _make_app()
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

        # Initially expanded
        assert len(list(widget.query(PRRow))) == 2

        # Collapse via left arrow
        await pilot.press("left")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 0


@pytest.mark.asyncio
async def test_right_on_expanded_group_noop(sample_pr):
    """Right arrow on already-expanded group should not change anything."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test Group",
                group_type="test",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        assert len(list(widget.query(PRRow))) == 1

        await pilot.press("right")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 1


@pytest.mark.asyncio
async def test_left_on_collapsed_group_noop(sample_pr):
    """Left arrow on already-collapsed group should not change anything."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test Group",
                group_type="test",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Collapse first
        await pilot.press("enter")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 0

        # Left on already-collapsed — no change
        await pilot.press("left")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 0


@pytest.mark.asyncio
async def test_left_right_on_pr_row_no_action(sample_pr):
    """Left/right arrows on a PR row should not collapse/expand anything."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test Group",
                group_type="test",
                pull_requests=[sample_pr],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move to PR row
        await pilot.press("j")
        await pilot.pause()

        # Left/right should not affect the group
        await pilot.press("left")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 1

        await pilot.press("right")
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 1


@pytest.mark.asyncio
async def test_no_username_no_approved_class():
    """Without a username, no rows should get pr-row-approved class."""
    approved_pr = _make_pr_with_reviewers("PR_A", 1, "Approved PR", [Reviewer(login="me", state="APPROVED")])
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data(
            [QueryGroupResult(group_name="Review Requested", group_type="review_requested", pull_requests=[approved_pr])],
        )
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].approved_by_me is False
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-approved" not in label.classes


# --- BranchRow tests (T30) ---


def _make_branch(name: str = "feat/test") -> CandidateBranch:
    from datetime import UTC, datetime, timedelta
    return CandidateBranch(
        name=name,
        repo_slug="org/repo",
        last_commit_date=datetime.now(UTC) - timedelta(hours=2),
        compare_url=f"https://github.com/org/repo/compare/feat%2Ftest?expand=1",
    )


@pytest.mark.asyncio
async def test_branch_row_renders_name_and_label():
    """BranchRow should display the branch name and 'ready to PR' label."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        rows = list(widget.query(BranchRow))
        assert len(rows) == 1
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        content = str(label.content)
        assert "feat/test" in content
        assert "ready to PR" in content


@pytest.mark.asyncio
async def test_group_header_count_includes_branches(sample_pr):
    """Group header count should include both PRs and branches."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Mixed",
                group_type="test",
                pull_requests=[sample_pr],
                branches=[branch],
            ),
        ])
        await pilot.pause()

        headers = list(widget.query(GroupHeaderItem))
        assert headers[0].count == 2  # 1 PR + 1 branch


@pytest.mark.asyncio
async def test_enter_on_branch_row_opens_compare_url():
    """Pressing Enter on a BranchRow should open the compare URL."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move to the BranchRow (index 0 is header, 1 is branch)
        await pilot.press("j")
        await pilot.pause()

        with patch("prdash.widgets.pr_list.webbrowser.open") as mock_open:
            await pilot.press("enter")
            await pilot.pause()
            mock_open.assert_called_once_with(branch.compare_url)


@pytest.mark.asyncio
async def test_highlight_branch_row_posts_branch_selected():
    """Highlighting a BranchRow should post a BranchSelected message."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        list_view = widget.query_one(NavigableListView)
        list_view.focus()
        await pilot.pause()

        # Move to the branch row
        await pilot.press("j")
        await pilot.pause()

        # Verify detail pane updated (BranchSelected -> show_branch)
        from textual.widgets import Static
        meta = pilot.app.query_one("#detail-metadata", Static)
        assert "hidden" not in meta.classes
        content = str(meta.content)
        assert "feat/test" in content


# --- Draft PR badge tests (T36) ---


def _make_draft_pr(is_draft: bool = True) -> PullRequest:
    from datetime import UTC, datetime, timedelta
    return PullRequest(
        id="PR_DRAFT",
        number=50,
        title="WIP: draft feature",
        author="alice",
        url="https://github.com/org/repo/pull/50",
        created_at=datetime.now(UTC) - timedelta(hours=1),
        is_draft=is_draft,
    )


@pytest.mark.asyncio
async def test_draft_pr_row_renders_draft_badge():
    """A draft PR should render a DRAFT badge in the metadata line."""
    app = _make_app()
    draft_pr = _make_draft_pr(is_draft=True)
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test",
                group_type="test",
                pull_requests=[draft_pr],
            ),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 1
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "DRAFT" in str(label_static.content)


@pytest.mark.asyncio
async def test_non_draft_pr_row_no_draft_badge():
    """A non-draft PR should not render a DRAFT badge."""
    app = _make_app()
    non_draft_pr = _make_draft_pr(is_draft=False)
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Test",
                group_type="test",
                pull_requests=[non_draft_pr],
            ),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 1
        from textual.widgets import Static
        label_static = rows[0].query_one(".pr-row-label", Static)
        assert "DRAFT" not in str(label_static.content)


# --- Ready-to-merge highlight tests (T38) ---


def _make_mergeable_pr(merge_state_status: str = "CLEAN") -> PullRequest:
    from datetime import UTC, datetime, timedelta
    return PullRequest(
        id="PR_MERGE",
        number=60,
        title="Ready to merge PR",
        author="alice",
        url="https://github.com/org/repo/pull/60",
        created_at=datetime.now(UTC) - timedelta(hours=1),
        merge_state_status=merge_state_status,
    )


@pytest.mark.asyncio
async def test_clean_pr_in_authored_group_gets_ready_to_merge_class():
    """A CLEAN PR in an authored group should get pr-row-ready-to-merge class."""
    app = _make_app()
    pr = _make_mergeable_pr("CLEAN")
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(group_name="My PRs", group_type="authored", pull_requests=[pr]),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].ready_to_merge is True
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-ready-to-merge" in label.classes


@pytest.mark.asyncio
async def test_clean_pr_in_non_authored_group_no_ready_class():
    """A CLEAN PR in a non-authored group should NOT get pr-row-ready-to-merge class."""
    app = _make_app()
    pr = _make_mergeable_pr("CLEAN")
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(group_name="Review Requested", group_type="review_requested", pull_requests=[pr]),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].ready_to_merge is False
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-ready-to-merge" not in label.classes


@pytest.mark.asyncio
async def test_blocked_pr_in_authored_group_no_ready_class():
    """A BLOCKED PR in an authored group should NOT get pr-row-ready-to-merge class."""
    app = _make_app()
    pr = _make_mergeable_pr("BLOCKED")
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(group_name="My PRs", group_type="authored", pull_requests=[pr]),
        ])
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert rows[0].ready_to_merge is False
        from textual.widgets import Static
        label = rows[0].query_one(".pr-row-label", Static)
        assert "pr-row-ready-to-merge" not in label.classes


@pytest.mark.asyncio
async def test_group_with_only_branches_not_auto_collapsed():
    """A group with branches but no PRs should not be auto-collapsed."""
    app = _make_app()
    branch = _make_branch()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(
                group_name="Ready to PR",
                group_type="ready_to_pr",
                branches=[branch],
            ),
        ])
        await pilot.pause()

        headers = list(widget.query(GroupHeaderItem))
        assert headers[0].collapsed is False
        rows = list(widget.query(BranchRow))
        assert len(rows) == 1


# --- Filter tests (T42) ---


def test_filter_binding_exists():
    """PRListWidget should have a slash binding for filter."""
    keys = [b.key for b in PRListWidget.BINDINGS]
    assert "slash" in keys


@pytest.mark.asyncio
async def test_filter_hides_non_matching_prs(sample_pr, sample_pr_minimal):
    """Filtering should hide PRs that don't match."""
    app = _make_app()
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

        # Both PRs visible
        assert len(list(widget.query(PRRow))) == 2

        # Apply filter matching only sample_pr (title: "Fix auth token refresh")
        widget._filter_query = "auth"
        widget._rebuild_list()
        await pilot.pause()

        rows = list(widget.query(PRRow))
        assert len(rows) == 1
        assert rows[0].pr.id == sample_pr.id


@pytest.mark.asyncio
async def test_filter_hides_empty_groups(sample_pr):
    """Groups with no matching PRs should be hidden when filter is active."""
    app = _make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(PRListWidget)
        widget.update_data([
            QueryGroupResult(group_name="Group A", group_type="test", pull_requests=[sample_pr]),
            QueryGroupResult(group_name="Group B", group_type="test", pull_requests=[]),
        ])
        await pilot.pause()

        # Filter to something only in group A
        widget._filter_query = "auth"
        widget._rebuild_list()
        await pilot.pause()

        headers = list(widget.query(GroupHeaderItem))
        assert len(headers) == 1
        assert headers[0].group_name == "Group A"


@pytest.mark.asyncio
async def test_clearing_filter_restores_all(sample_pr, sample_pr_minimal):
    """Clearing filter should show all PRs again."""
    app = _make_app()
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

        # Filter then clear
        widget._filter_query = "auth"
        widget._rebuild_list()
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 1

        widget._filter_query = ""
        widget._rebuild_list()
        await pilot.pause()
        assert len(list(widget.query(PRRow))) == 2


# --- Checkout tests (T48) ---


@pytest.mark.asyncio
async def test_c_key_binding_exists():
    """NavigableListView should have a 'c' binding."""
    keys = [b.key for b in NavigableListView.BINDINGS]
    assert "c" in keys


@pytest.mark.asyncio
async def test_checkout_pr_calls_gh(sample_pr):
    """Pressing c on a PR row should invoke gh pr checkout."""
    app = _make_app()
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

        # Move to PR row
        await pilot.press("j")
        await pilot.pause()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("prdash.widgets.pr_list.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await pilot.press("c")
            await pilot.pause()
            await pilot.pause()
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "gh"
            assert str(sample_pr.number) in args



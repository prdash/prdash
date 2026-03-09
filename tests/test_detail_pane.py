"""Tests for the detail pane widget."""

from datetime import UTC, datetime, timedelta

import pytest

from gh_review_dashboard.models import PullRequest
from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.widgets.detail_pane import (
    DetailPaneWidget,
    _format_checks,
    _format_description,
    _format_labels,
    _format_reviewers,
    _format_timeline,
)


@pytest.mark.asyncio
async def test_detail_pane_exists_in_app():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        widget = pilot.app.query_one(DetailPaneWidget)
        assert widget is not None


@pytest.mark.asyncio
async def test_detail_pane_shows_placeholder_initially():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        placeholder = pilot.app.query_one("#detail-placeholder")
        assert "hidden" not in placeholder.classes
        # Detail sections should all be hidden initially
        sections = pilot.app.query(".detail-section")
        for s in sections:
            assert "hidden" in s.classes


@pytest.mark.asyncio
async def test_show_pr_hides_placeholder(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_pr(sample_pr)
        await pilot.pause()

        placeholder = pilot.app.query_one("#detail-placeholder")
        assert "hidden" in placeholder.classes


@pytest.mark.asyncio
async def test_show_pr_displays_metadata(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_pr(sample_pr)
        await pilot.pause()

        meta = pilot.app.query_one("#detail-metadata")
        assert "hidden" not in meta.classes


@pytest.mark.asyncio
async def test_show_pr_displays_sections(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_pr(sample_pr)
        await pilot.pause()

        for section_id in [
            "#detail-description",
            "#detail-labels",
            "#detail-reviewers",
            "#detail-checks",
            "#detail-timeline",
        ]:
            widget = pilot.app.query_one(section_id)
            assert "hidden" not in widget.classes


@pytest.mark.asyncio
async def test_clear_restores_placeholder(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_pr(sample_pr)
        await pilot.pause()

        detail.clear()
        await pilot.pause()

        placeholder = pilot.app.query_one("#detail-placeholder")
        assert "hidden" not in placeholder.classes

        sections = pilot.app.query(".detail-section")
        for s in sections:
            assert "hidden" in s.classes


@pytest.mark.asyncio
async def test_section_order_reviewers_before_description():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        scroll = pilot.app.query_one("#detail-scroll")
        children_ids = [c.id for c in scroll.children if c.id]
        reviewers_idx = children_ids.index("detail-reviewers")
        description_idx = children_ids.index("detail-description")
        assert reviewers_idx < description_idx


# --- Unit tests for formatters ---


def test_format_description_with_body(sample_pr):
    assert "fixes the auth" in _format_description(sample_pr)


def test_format_description_no_body(sample_pr_minimal):
    assert "*No description provided.*" in _format_description(sample_pr_minimal)


def test_format_labels(sample_pr):
    result = _format_labels(sample_pr)
    assert "bug" in result
    assert "auth" in result


def test_format_labels_empty(sample_pr_minimal):
    assert _format_labels(sample_pr_minimal) == "None"


def test_format_reviewers(sample_pr):
    result = _format_reviewers(sample_pr)
    assert "✓ bob — approved" in result
    assert "○ carol — pending" in result


def test_format_reviewers_empty(sample_pr_minimal):
    assert _format_reviewers(sample_pr_minimal) == "None"


def test_format_reviewers_unknown_state():
    from gh_review_dashboard.models import Reviewer

    pr = PullRequest(
        id="PR_3",
        number=50,
        title="Test",
        author="alice",
        url="https://github.com/org/repo/pull/50",
        created_at=datetime.now(UTC) - timedelta(hours=1),
        reviewers=[Reviewer(login="dave", state="STALE")],
    )
    result = _format_reviewers(pr)
    assert "? dave — STALE" in result


def test_format_checks(sample_pr):
    result = _format_checks(sample_pr)
    assert "unit-tests" in result
    assert "lint" in result
    assert "SUCCESS" in result
    assert "FAILURE" in result


def test_format_checks_empty(sample_pr_minimal):
    assert _format_checks(sample_pr_minimal) == "None"


def test_format_timeline(sample_pr):
    result = _format_timeline(sample_pr)
    assert "commented" in result
    assert "reviewed" in result
    assert "force" in result


def test_format_timeline_empty(sample_pr_minimal):
    assert _format_timeline(sample_pr_minimal) == "None"

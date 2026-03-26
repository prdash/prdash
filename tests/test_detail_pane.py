"""Tests for the detail pane widget."""

from datetime import UTC, datetime, timedelta

import pytest

from prdash.models import (
    BranchCommit,
    BranchFileChange,
    CandidateBranch,
    PullRequest,
)
from prdash.app import ReviewDashboardApp
from prdash.widgets.detail_pane import (
    DetailPaneWidget,
    _format_branch_commits,
    _format_branch_files,
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
    from prdash.models import Reviewer

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


# --- Branch detail helpers ---


def _make_branch(**kwargs) -> CandidateBranch:
    defaults = {
        "name": "feat/test",
        "repo_slug": "org/repo",
        "last_commit_date": datetime.now(UTC) - timedelta(hours=2),
        "compare_url": "https://github.com/org/repo/compare/feat%2Ftest?expand=1",
        "default_branch": "main",
    }
    defaults.update(kwargs)
    return CandidateBranch(**defaults)


def _make_commits(n: int) -> list[BranchCommit]:
    return [
        BranchCommit(
            sha=f"sha{i:010d}",
            short_sha=f"sha{i:04d}",
            message=f"commit {i}",
            authored_date=datetime.now(UTC) - timedelta(hours=i),
        )
        for i in range(n)
    ]


def _make_files(n: int) -> list[BranchFileChange]:
    return [
        BranchFileChange(
            filename=f"src/file{i}.py",
            additions=i + 1,
            deletions=i,
            status="modified",
        )
        for i in range(n)
    ]


# --- _format_branch_commits ---


class TestFormatBranchCommits:
    def test_empty(self) -> None:
        branch = _make_branch()
        assert _format_branch_commits(branch) == ""

    def test_normal(self) -> None:
        branch = _make_branch(
            commits=_make_commits(3),
            total_commits=3,
        )
        result = _format_branch_commits(branch)
        assert "--- Commits ---" in result
        assert "commit 0" in result
        assert "commit 2" in result
        assert "… and" not in result

    def test_truncated(self) -> None:
        branch = _make_branch(
            commits=_make_commits(10),
            total_commits=25,
        )
        result = _format_branch_commits(branch)
        assert "… and 15 more" in result


# --- _format_branch_files ---


class TestFormatBranchFiles:
    def test_empty(self) -> None:
        branch = _make_branch()
        assert _format_branch_files(branch) == ""

    def test_normal(self) -> None:
        branch = _make_branch(
            files=_make_files(3),
            total_files=3,
            total_additions=6,
            total_deletions=3,
        )
        result = _format_branch_files(branch)
        assert "--- Files (3 changed, +6 -3) ---" in result
        assert "src/file0.py" in result
        assert "src/file2.py" in result
        assert "… and" not in result

    def test_truncated(self) -> None:
        branch = _make_branch(
            files=_make_files(30),
            total_files=50,
            total_additions=100,
            total_deletions=50,
        )
        result = _format_branch_files(branch)
        assert "… and 20 more" in result

    def test_file_status_icons(self) -> None:
        branch = _make_branch(
            files=[
                BranchFileChange(filename="a.py", additions=1, deletions=0, status="added"),
                BranchFileChange(filename="b.py", additions=0, deletions=1, status="removed"),
                BranchFileChange(filename="c.py", additions=1, deletions=1, status="renamed"),
            ],
            total_files=3,
            total_additions=2,
            total_deletions=2,
        )
        result = _format_branch_files(branch)
        lines = result.split("\n")
        assert any("+" in l and "a.py" in l for l in lines)
        assert any("-" in l and "b.py" in l for l in lines)
        assert any("→" in l and "c.py" in l for l in lines)


# --- Textual integration tests for branch detail ---


@pytest.mark.asyncio
async def test_show_branch_renders_commits():
    branch = _make_branch(
        commits=_make_commits(2),
        total_commits=2,
    )
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_branch(branch)
        await pilot.pause()

        commits_widget = pilot.app.query_one("#detail-commits")
        assert "hidden" not in commits_widget.classes


@pytest.mark.asyncio
async def test_show_branch_renders_files():
    branch = _make_branch(
        files=_make_files(2),
        total_files=2,
        total_additions=3,
        total_deletions=1,
    )
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_branch(branch)
        await pilot.pause()

        files_widget = pilot.app.query_one("#detail-files")
        assert "hidden" not in files_widget.classes


@pytest.mark.asyncio
async def test_show_branch_hides_empty_commits_and_files():
    branch = _make_branch()
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_branch(branch)
        await pilot.pause()

        assert "hidden" in pilot.app.query_one("#detail-commits").classes
        assert "hidden" in pilot.app.query_one("#detail-files").classes


@pytest.mark.asyncio
async def test_show_pr_hides_branch_sections(sample_pr):
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = pilot.app.query_one(DetailPaneWidget)
        detail.show_pr(sample_pr)
        await pilot.pause()

        assert "hidden" in pilot.app.query_one("#detail-commits").classes
        assert "hidden" in pilot.app.query_one("#detail-files").classes

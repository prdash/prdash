import pytest

from gh_review_dashboard.app import ReviewDashboardApp
from gh_review_dashboard.widgets import DetailPaneWidget, PRListWidget


def test_app_title():
    app = ReviewDashboardApp()
    assert app.TITLE == "GitHub Review Dashboard"


def test_app_css_path():
    app = ReviewDashboardApp()
    assert app.CSS_PATH == "app.tcss"


def test_app_has_quit_binding():
    app = ReviewDashboardApp()
    keys = [b[0] for b in app.BINDINGS]
    assert "q" in keys


@pytest.mark.asyncio
async def test_app_has_header_and_footer():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.widgets import Footer, Header

        headers = pilot.app.query(Header)
        assert len(headers) == 1
        footers = pilot.app.query(Footer)
        assert len(footers) == 1


@pytest.mark.asyncio
async def test_app_has_widget_panes():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        pr_list = pilot.app.query_one("#pr-list-pane", PRListWidget)
        assert pr_list is not None
        detail = pilot.app.query_one("#detail-pane", DetailPaneWidget)
        assert detail is not None


@pytest.mark.asyncio
async def test_app_horizontal_container_has_two_children():
    app = ReviewDashboardApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.containers import Horizontal

        horizontal = pilot.app.query_one(Horizontal)
        children = list(horizontal.children)
        assert len(children) == 2


@pytest.mark.asyncio
async def test_app_pr_selected_wires_to_detail_pane(sample_pr):
    app = ReviewDashboardApp()
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

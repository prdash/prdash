"""Textual widget modules for the dashboard."""

from gh_review_dashboard.widgets.detail_pane import DetailPaneWidget
from gh_review_dashboard.widgets.pr_list import (
    GroupHeaderItem,
    NavigableListView,
    PRListWidget,
    PRSelected,
)

__all__ = [
    "DetailPaneWidget",
    "GroupHeaderItem",
    "NavigableListView",
    "PRListWidget",
    "PRSelected",
]

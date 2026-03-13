"""Textual widget modules for the dashboard."""

from gh_review_dashboard.widgets.detail_pane import DetailPaneWidget
from gh_review_dashboard.widgets.pr_list import (
    BranchRow,
    BranchSelected,
    EmptyGroupItem,
    GroupHeaderItem,
    NavigableListView,
    PRListWidget,
    PRSelected,
)

__all__ = [
    "BranchRow",
    "BranchSelected",
    "DetailPaneWidget",
    "EmptyGroupItem",
    "GroupHeaderItem",
    "NavigableListView",
    "PRListWidget",
    "PRSelected",
]

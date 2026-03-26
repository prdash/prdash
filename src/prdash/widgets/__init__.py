"""Textual widget modules for the dashboard."""

from prdash.widgets.detail_pane import DetailPaneWidget
from prdash.widgets.pr_list import (
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

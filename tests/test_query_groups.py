"""Tests for the query groups management screen."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prdash.app import ReviewDashboardApp
from prdash.config import (
    AppConfig,
    QueryGroupConfig,
    QueryGroupType,
)
from prdash.screens.query_groups import QueryGroupsScreen
from prdash.screens.settings import SettingsScreen


def _make_config(**overrides: object) -> AppConfig:
    defaults: dict = {
        "repos": ["test-org/test-repo"],
        "username": "testuser",
        "team_slugs": ["team-a"],
        "poll_interval": 300,
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _sample_groups() -> list[QueryGroupConfig]:
    return [
        QueryGroupConfig(
            type=QueryGroupType.DIRECT_REVIEWER, name="Direct", enabled=True
        ),
        QueryGroupConfig(
            type=QueryGroupType.TEAM_REVIEWER, name="Team", enabled=True
        ),
        QueryGroupConfig(
            type=QueryGroupType.LABEL,
            name="Labeled",
            labels=["bug", "urgent"],
            enabled=False,
        ),
    ]


class TestQueryGroupsScreen:
    @pytest.mark.asyncio
    async def test_groups_display_on_mount(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(QueryGroupsScreen(groups))
            await pilot.pause()

            from textual.widgets import Switch

            switches = app.screen.query(Switch)
            assert len(switches) == 3

    @pytest.mark.asyncio
    async def test_toggle_enabled(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            from textual.widgets import Switch

            # Toggle the first group off
            switch = app.screen.query_one("#switch-0", Switch)
            switch.value = False
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            assert len(result_holder) == 1
            saved = result_holder[0]
            assert saved is not None
            assert saved[0].enabled is False
            assert saved[1].enabled is True

    @pytest.mark.asyncio
    async def test_remove_group(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            # Remove the second group (Team)
            await pilot.click("#remove-1")
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            saved = result_holder[0]
            assert len(saved) == 2
            assert saved[0].name == "Direct"
            assert saved[1].name == "Labeled"

    @pytest.mark.asyncio
    async def test_move_up(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            # Move second group up
            await pilot.click("#up-1")
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            saved = result_holder[0]
            assert saved[0].name == "Team"
            assert saved[1].name == "Direct"

    @pytest.mark.asyncio
    async def test_move_down(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            # Move first group down
            await pilot.click("#down-0")
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            saved = result_holder[0]
            assert saved[0].name == "Team"
            assert saved[1].name == "Direct"

    @pytest.mark.asyncio
    async def test_add_group(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            # Click "Add Group" to reveal the form
            await pilot.click("#add-group-btn")
            await pilot.pause()

            from textual.widgets import Input, Select

            # Fill in the form
            app.screen.query_one("#add-type-select", Select).value = (
                QueryGroupType.MENTIONED
            )
            app.screen.query_one("#add-name-input", Input).value = "My Mentions"
            await pilot.pause()

            await pilot.click("#confirm-add-btn")
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            saved = result_holder[0]
            assert len(saved) == 4
            assert saved[3].name == "My Mentions"
            assert saved[3].type == QueryGroupType.MENTIONED
            assert saved[3].enabled is True

    @pytest.mark.asyncio
    async def test_save_returns_updated_list(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            await pilot.click("#qg-save-btn")
            await pilot.pause()

            assert len(result_holder) == 1
            assert result_holder[0] is not None
            assert len(result_holder[0]) == 3

    @pytest.mark.asyncio
    async def test_cancel_returns_none(self) -> None:
        groups = _sample_groups()
        config = _make_config()
        result_holder: list = []
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(
                QueryGroupsScreen(groups), callback=result_holder.append
            )
            await pilot.pause()

            await pilot.click("#qg-cancel-btn")
            await pilot.pause()

            assert result_holder == [None]

    @pytest.mark.asyncio
    async def test_does_not_mutate_original(self) -> None:
        groups = _sample_groups()
        original_len = len(groups)
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(QueryGroupsScreen(groups))
            await pilot.pause()

            # Remove a group
            await pilot.click("#remove-0")
            await pilot.pause()

        # Original list should not be modified
        assert len(groups) == original_len


class TestQueryGroupsFromSettings:
    @pytest.mark.asyncio
    async def test_query_groups_button_exists(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SettingsScreen(config))
            await pilot.pause()

            btn = app.screen.query_one("#query-groups-btn")
            assert btn is not None

    @pytest.mark.asyncio
    async def test_query_groups_button_opens_screen(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SettingsScreen(config))
            await pilot.pause()

            await pilot.click("#query-groups-btn")
            await pilot.pause()

            assert isinstance(app.screen, QueryGroupsScreen)

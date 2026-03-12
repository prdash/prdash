"""Tests for the in-app settings screen."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_review_dashboard.config import AppConfig
from gh_review_dashboard.screens.settings import SettingsScreen
from gh_review_dashboard.app import ReviewDashboardApp


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "repos": ["test-org/test-repo"],
        "username": "testuser",
        "team_slugs": ["team-a"],
        "poll_interval": 300,
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestSettingsScreen:
    @pytest.mark.asyncio
    async def test_prefilled_values(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(80, 24)) as pilot:
            screen = SettingsScreen(config)
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input

            assert screen.query_one("#repos-input", Input).value == "test-org/test-repo"
            assert screen.query_one("#username-input", Input).value == "testuser"
            assert screen.query_one("#teams-input", Input).value == "team-a"
            assert screen.query_one("#interval-input", Input).value == "300"

    @pytest.mark.asyncio
    async def test_cancel_dismisses_with_none(self) -> None:
        config = _make_config()
        result_holder: list = []

        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(SettingsScreen(config), callback=result_holder.append)
            await pilot.pause()

            await pilot.click("#cancel-btn")
            await pilot.pause()

            assert result_holder == [None]

    @pytest.mark.asyncio
    async def test_save_validates_required(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(80, 24)) as pilot:
            screen = SettingsScreen(config)
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input, Static

            screen.query_one("#username-input", Input).value = ""

            await pilot.click("#save-btn")
            await pilot.pause()

            error = screen.query_one("#error-msg", Static)
            assert "username" in str(error.render()).lower()

    @pytest.mark.asyncio
    async def test_save_validates_interval(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(80, 24)) as pilot:
            screen = SettingsScreen(config)
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input, Static

            screen.query_one("#interval-input", Input).value = "10"

            await pilot.click("#save-btn")
            await pilot.pause()

            error = screen.query_one("#error-msg", Static)
            assert "at least 30" in str(error.render()).lower()

    @pytest.mark.asyncio
    async def test_save_creates_config_and_dismisses(self) -> None:
        config = _make_config()
        result_holder: list = []

        app = ReviewDashboardApp(config=config)

        with patch("gh_review_dashboard.screens.settings.save_config") as mock_save:
            async with app.run_test(size=(80, 24)) as pilot:
                app.push_screen(
                    SettingsScreen(config), callback=result_holder.append
                )
                await pilot.pause()

                from textual.widgets import Input

                screen = app.screen
                screen.query_one("#interval-input", Input).value = "60"

                await pilot.click("#save-btn")
                await pilot.pause()

                mock_save.assert_called_once()
                assert len(result_holder) == 1
                new_config = result_holder[0]
                assert new_config is not None
                assert new_config.poll_interval == 60


class TestSettingsIntegration:
    @pytest.mark.asyncio
    async def test_s_keybinding_opens_settings(self) -> None:
        config = _make_config()
        app = ReviewDashboardApp(config=config)

        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("S")
            await pilot.pause()

            assert isinstance(app.screen, SettingsScreen)

    @pytest.mark.asyncio
    async def test_settings_save_updates_config_and_triggers_refresh(self) -> None:
        config = _make_config()
        mock_client = MagicMock()
        mock_client.fetch_all_groups = AsyncMock(return_value=[])
        app = ReviewDashboardApp(config=config, github_client=mock_client)

        with patch("gh_review_dashboard.screens.settings.save_config"):
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.press("S")
                await pilot.pause()

                from textual.widgets import Input

                app.screen.query_one("#interval-input", Input).value = "60"

                await pilot.click("#save-btn")
                await pilot.pause()

                assert app.config is not None
                assert app.config.poll_interval == 60

"""Tests for setup wizard screens."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from prdash.screens.setup_wizard import (
    PollIntervalScreen,
    RepoScreen,
    SetupWizardApp,
    TeamSlugsScreen,
    UsernameScreen,
    WizardState,
)


@pytest.fixture
def _no_detection():
    """Prevent SetupWizardApp.on_mount from running auto-detection."""
    with patch.object(
        SetupWizardApp, "_run_detection", lambda self: None,
    ):
        yield


@pytest.fixture
def wizard_state() -> WizardState:
    return WizardState()


@pytest.fixture
def prefilled_state() -> WizardState:
    return WizardState(
        org="test-org",
        repo_name="test-repo",
        username="testuser",
        team_slugs=["backend"],
        detected_team_slugs=["backend", "frontend"],
    )


@pytest.mark.usefixtures("_no_detection")
class TestRepoScreen:
    @pytest.mark.asyncio
    async def test_prefilled_values_shown(self, prefilled_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = prefilled_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = RepoScreen(prefilled_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input

            org_input = screen.query_one("#org-input", Input)
            repo_input = screen.query_one("#repo-input", Input)
            assert org_input.value == "test-org"
            assert repo_input.value == "test-repo"

    @pytest.mark.asyncio
    async def test_empty_fields_show_error(self, wizard_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = wizard_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = RepoScreen(wizard_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            await pilot.click("#next-btn")
            await pilot.pause()

            from textual.widgets import Static

            error = screen.query_one("#error-msg", Static)
            assert "required" in str(error.render()).lower()

    @pytest.mark.asyncio
    async def test_advance_saves_state(self, wizard_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = wizard_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = RepoScreen(wizard_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input

            org_input = screen.query_one("#org-input", Input)
            repo_input = screen.query_one("#repo-input", Input)
            org_input.value = "my-org"
            repo_input.value = "my-repo"

            await pilot.click("#next-btn")
            await pilot.pause()

            assert wizard_state.org == "my-org"
            assert wizard_state.repo_name == "my-repo"


@pytest.mark.usefixtures("_no_detection")
class TestUsernameScreen:
    @pytest.mark.asyncio
    async def test_advance_saves_username(self, wizard_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = wizard_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = UsernameScreen(wizard_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input

            username_input = screen.query_one("#username-input", Input)
            username_input.value = "octocat"

            await pilot.click("#next-btn")
            await pilot.pause()

            assert wizard_state.username == "octocat"

    @pytest.mark.asyncio
    async def test_empty_username_shows_error(self, wizard_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = wizard_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = UsernameScreen(wizard_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            await pilot.click("#next-btn")
            await pilot.pause()

            from textual.widgets import Static

            error = screen.query_one("#error-msg", Static)
            assert "required" in str(error.render()).lower()


@pytest.mark.usefixtures("_no_detection")
class TestTeamSlugsScreen:
    @pytest.mark.asyncio
    async def test_text_input_mode_when_no_detected(self, wizard_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = wizard_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = TeamSlugsScreen(wizard_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input

            teams_input = screen.query_one("#teams-input", Input)
            teams_input.value = "backend, frontend"

            await pilot.click("#next-btn")
            await pilot.pause()

            assert wizard_state.team_slugs == ["backend", "frontend"]

    @pytest.mark.asyncio
    async def test_checkbox_mode_with_detected(self, prefilled_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = prefilled_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = TeamSlugsScreen(prefilled_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Checkbox

            # Both checkboxes should be present
            cb_backend = screen.query_one("#team-backend", Checkbox)
            cb_frontend = screen.query_one("#team-frontend", Checkbox)
            assert cb_backend.value is True  # was in team_slugs
            assert cb_frontend.value is False  # not in team_slugs


@pytest.mark.usefixtures("_no_detection")
class TestPollIntervalScreen:
    @pytest.mark.asyncio
    async def test_invalid_number_shows_error(self, prefilled_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = prefilled_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = PollIntervalScreen(prefilled_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input, Static

            interval_input = screen.query_one("#interval-input", Input)
            interval_input.value = "abc"

            await pilot.click("#finish-btn")
            await pilot.pause()

            error = screen.query_one("#error-msg", Static)
            assert "valid number" in str(error.render()).lower()

    @pytest.mark.asyncio
    async def test_too_low_shows_error(self, prefilled_state: WizardState) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = prefilled_state

        async with app.run_test(size=(80, 24)) as pilot:
            screen = PollIntervalScreen(prefilled_state, "ghp_test")
            app.push_screen(screen)
            await pilot.pause()

            from textual.widgets import Input, Static

            interval_input = screen.query_one("#interval-input", Input)
            interval_input.value = "10"

            await pilot.click("#finish-btn")
            await pilot.pause()

            error = screen.query_one("#error-msg", Static)
            assert "at least 30" in str(error.render()).lower()

    @pytest.mark.asyncio
    async def test_finish_saves_config(self, prefilled_state: WizardState, tmp_path) -> None:
        app = SetupWizardApp(token="ghp_test")
        app.wizard_state = prefilled_state

        with patch("prdash.screens.setup_wizard.save_config") as mock_save:
            async with app.run_test(size=(80, 24)) as pilot:
                screen = PollIntervalScreen(prefilled_state, "ghp_test")
                app.push_screen(screen)
                await pilot.pause()

                from textual.widgets import Input

                interval_input = screen.query_one("#interval-input", Input)
                interval_input.value = "120"

                await pilot.click("#finish-btn")
                await pilot.pause()

                assert prefilled_state.poll_interval == 120
                assert prefilled_state.completed is True
                mock_save.assert_called_once()
                saved_config = mock_save.call_args[0][0]
                assert saved_config.repos == ["test-org/test-repo"]
                assert saved_config.username == "testuser"
                assert saved_config.poll_interval == 120


class TestSetupWizardApp:
    @pytest.mark.asyncio
    async def test_detection_populates_state(self) -> None:
        with (
            patch(
                "prdash.screens.setup_wizard.detect_repo_from_git_remote",
                return_value=("detected-org", "detected-repo"),
            ),
            patch(
                "prdash.screens.setup_wizard.detect_username",
                new_callable=AsyncMock,
                return_value="detected-user",
            ),
            patch(
                "prdash.screens.setup_wizard.detect_team_slugs",
                new_callable=AsyncMock,
                return_value=["team-a"],
            ),
        ):
            app = SetupWizardApp(token="ghp_test")
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()  # let worker complete

                assert app.wizard_state.org == "detected-org"
                assert app.wizard_state.repo_name == "detected-repo"
                assert app.wizard_state.username == "detected-user"
                assert app.wizard_state.detected_team_slugs == ["team-a"]

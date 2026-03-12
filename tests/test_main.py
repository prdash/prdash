"""Tests for __main__.py entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gh_review_dashboard.__main__ import main
from gh_review_dashboard.exceptions import AuthError


class TestMain:
    def test_auth_failure_exits(self) -> None:
        with patch(
            "gh_review_dashboard.__main__.get_github_token",
            side_effect=AuthError("no token"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_wizard_launched_when_no_config(self, tmp_path) -> None:
        mock_wizard = MagicMock()
        mock_wizard.wizard_state.completed = False

        with (
            patch("gh_review_dashboard.__main__.get_github_token", return_value="ghp_test"),
            patch("gh_review_dashboard.__main__.CONFIG_FILE", tmp_path / "nonexistent.toml"),
            patch("gh_review_dashboard.__main__.SetupWizardApp", return_value=mock_wizard),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_wizard.run.assert_called_once()

    def test_wizard_skipped_when_config_exists(self, tmp_path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'username = "user"\nrepos = ["org/repo"]\n'
        )

        mock_app = MagicMock()

        with (
            patch("gh_review_dashboard.__main__.get_github_token", return_value="ghp_test"),
            patch("gh_review_dashboard.__main__.CONFIG_FILE", config_file),
            patch("gh_review_dashboard.__main__.load_config") as mock_load,
            patch("gh_review_dashboard.__main__.create_http_client"),
            patch("gh_review_dashboard.__main__.GitHubClient"),
            patch("gh_review_dashboard.__main__.ReviewDashboardApp", return_value=mock_app),
        ):
            mock_load.return_value = MagicMock()
            main()
            mock_app.run.assert_called_once()

    def test_wizard_completed_proceeds_to_dashboard(self, tmp_path) -> None:
        config_file = tmp_path / "config.toml"
        # Simulate wizard creating the file
        config_file.write_text(
            'username = "user"\nrepos = ["org/repo"]\n'
        )

        mock_wizard = MagicMock()
        mock_wizard.wizard_state.completed = True

        mock_app = MagicMock()

        with (
            patch("gh_review_dashboard.__main__.get_github_token", return_value="ghp_test"),
            patch("gh_review_dashboard.__main__.CONFIG_FILE", config_file),
            patch("gh_review_dashboard.__main__.load_config") as mock_load,
            patch("gh_review_dashboard.__main__.create_http_client"),
            patch("gh_review_dashboard.__main__.GitHubClient"),
            patch("gh_review_dashboard.__main__.ReviewDashboardApp", return_value=mock_app),
        ):
            mock_load.return_value = MagicMock()
            main()
            mock_app.run.assert_called_once()

"""Tests for updater module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from prdash.updater import (
    InstallMethod,
    _is_homebrew,
    detect_install_method,
    get_version,
    run_upgrade,
)


class TestGetVersion:
    def test_returns_installed_version(self) -> None:
        with patch(
            "prdash.updater.version",
            return_value="1.2.3",
        ):
            assert get_version() == "1.2.3"

    def test_returns_dev_when_not_installed(self) -> None:
        from importlib.metadata import PackageNotFoundError

        with patch(
            "prdash.updater.version",
            side_effect=PackageNotFoundError,
        ):
            assert get_version() == "dev"


class TestIsHomebrew:
    def test_cellar_path(self) -> None:
        with patch("prdash.updater.sys") as mock_sys:
            mock_sys.prefix = "/opt/homebrew/Cellar/prdash/0.1.0/libexec"
            assert _is_homebrew() is True

    def test_homebrew_linuxbrew_path(self) -> None:
        with patch("prdash.updater.sys") as mock_sys:
            mock_sys.prefix = "/home/user/.linuxbrew/Homebrew/lib/prdash"
            assert _is_homebrew() is True  # Linuxbrew is Homebrew

    def test_homebrew_lowercase_path(self) -> None:
        with patch("prdash.updater.sys") as mock_sys:
            mock_sys.prefix = "/usr/local/Homebrew/Cellar/prdash/0.1.0/libexec"
            assert _is_homebrew() is True

    def test_non_homebrew_path(self) -> None:
        with patch("prdash.updater.sys") as mock_sys:
            mock_sys.prefix = "/home/user/.local/share/uv/tools/prdash"
            assert _is_homebrew() is False

    def test_venv_path(self) -> None:
        with patch("prdash.updater.sys") as mock_sys:
            mock_sys.prefix = "/Users/user/dev/prdash/.venv"
            assert _is_homebrew() is False


class TestDetectInstallMethod:
    def test_detects_homebrew(self) -> None:
        with patch("prdash.updater._is_homebrew", return_value=True):
            assert detect_install_method() == InstallMethod.HOMEBREW

    def test_detects_uv_tool(self) -> None:
        result = MagicMock()
        result.stdout = "prdash-tui v0.1.0\nother-tool v1.0\n"
        with patch("subprocess.run", return_value=result):
            assert detect_install_method() == InstallMethod.UV_TOOL

    def test_detects_pipx(self) -> None:
        uv_result = MagicMock()
        uv_result.stdout = "other-tool v1.0\n"

        pipx_result = MagicMock()
        pipx_result.stdout = "prdash-tui 0.1.0\n"

        with patch("subprocess.run", side_effect=[uv_result, pipx_result]):
            assert detect_install_method() == InstallMethod.PIPX

    def test_falls_back_to_pip(self) -> None:
        uv_result = MagicMock()
        uv_result.stdout = "other-tool v1.0\n"

        pipx_result = MagicMock()
        pipx_result.stdout = "other-tool 1.0\n"

        with patch("subprocess.run", side_effect=[uv_result, pipx_result]):
            assert detect_install_method() == InstallMethod.PIP

    def test_uv_not_installed(self) -> None:
        pipx_result = MagicMock()
        pipx_result.stdout = "prdash-tui 0.1.0\n"

        with patch(
            "subprocess.run",
            side_effect=[FileNotFoundError, pipx_result],
        ):
            assert detect_install_method() == InstallMethod.PIPX

    def test_both_not_installed(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=[FileNotFoundError, FileNotFoundError],
        ):
            assert detect_install_method() == InstallMethod.PIP

    def test_uv_command_fails(self) -> None:
        pipx_result = MagicMock()
        pipx_result.stdout = "prdash-tui 0.1.0\n"

        with patch(
            "subprocess.run",
            side_effect=[subprocess.CalledProcessError(1, "uv"), pipx_result],
        ):
            assert detect_install_method() == InstallMethod.PIPX


class TestRunUpgrade:
    def test_homebrew_prints_message(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        run_upgrade(InstallMethod.HOMEBREW)
        captured = capsys.readouterr()
        assert "brew upgrade prdash" in captured.out

    def test_homebrew_does_not_run_subprocess(self) -> None:
        with patch("subprocess.run") as mock_run:
            run_upgrade(InstallMethod.HOMEBREW)
        mock_run.assert_not_called()

    def test_uv_tool_upgrade(self) -> None:
        with patch("subprocess.run") as mock_run:
            run_upgrade(InstallMethod.UV_TOOL)
        mock_run.assert_called_once_with(
            ["uv", "tool", "upgrade", "prdash-tui"],
            check=True,
        )

    def test_pipx_upgrade(self) -> None:
        with patch("subprocess.run") as mock_run:
            run_upgrade(InstallMethod.PIPX)
        mock_run.assert_called_once_with(
            ["pipx", "upgrade", "prdash-tui"],
            check=True,
        )

    def test_pip_upgrade(self) -> None:
        with patch("subprocess.run") as mock_run:
            run_upgrade(InstallMethod.PIP)
        args = mock_run.call_args[0][0]
        assert args[-3:] == ["install", "--upgrade", "prdash-tui"]
        assert "-m" in args
        assert "pip" in args

    def test_auto_detects_method(self) -> None:
        with (
            patch(
                "prdash.updater.detect_install_method",
                return_value=InstallMethod.UV_TOOL,
            ),
            patch("subprocess.run") as mock_run,
        ):
            run_upgrade()
        mock_run.assert_called_once_with(
            ["uv", "tool", "upgrade", "prdash-tui"],
            check=True,
        )

    def test_prints_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("subprocess.run"):
            run_upgrade(InstallMethod.UV_TOOL)
        captured = capsys.readouterr()
        assert "uv tool upgrade prdash-tui" in captured.out

    def test_file_not_found_exits_1(self) -> None:
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_upgrade(InstallMethod.UV_TOOL)
        assert exc_info.value.code == 1

    def test_called_process_error_exits_with_returncode(self) -> None:
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(42, "uv"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_upgrade(InstallMethod.UV_TOOL)
        assert exc_info.value.code == 42

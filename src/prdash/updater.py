"""Version checking and self-update logic."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed package version, or 'dev' if not installed."""
    try:
        return version("prdash")
    except PackageNotFoundError:
        return "dev"


class InstallMethod(Enum):
    HOMEBREW = "homebrew"
    UV_TOOL = "uv_tool"
    PIPX = "pipx"
    PIP = "pip"


def _is_homebrew() -> bool:
    """Check if running inside a Homebrew-managed virtualenv."""
    prefix = sys.prefix
    return "/Cellar/" in prefix or "/homebrew/" in prefix.lower()


def detect_install_method() -> InstallMethod:
    """Detect how prdash was installed."""
    if _is_homebrew():
        return InstallMethod.HOMEBREW

    # Try uv tool list
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "prdash" in result.stdout:
            return InstallMethod.UV_TOOL
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Try pipx list
    try:
        result = subprocess.run(
            ["pipx", "list", "--short"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "prdash" in result.stdout:
            return InstallMethod.PIPX
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return InstallMethod.PIP


def run_upgrade(method: InstallMethod | None = None) -> None:
    """Run the appropriate upgrade command for the detected install method."""
    if method is None:
        method = detect_install_method()

    if method is InstallMethod.HOMEBREW:
        print("Installed via Homebrew. Run: brew upgrade prdash")
        return

    commands: dict[InstallMethod, list[str]] = {
        InstallMethod.UV_TOOL: ["uv", "tool", "upgrade", "prdash"],
        InstallMethod.PIPX: ["pipx", "upgrade", "prdash"],
        InstallMethod.PIP: [
            sys.executable, "-m", "pip", "install", "--upgrade", "prdash",
        ],
    }

    cmd = commands[method]
    print(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(f"Error: '{cmd[0]}' not found. Is it installed?", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

"""Version checking and self-update logic."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed package version, or 'dev' if not installed."""
    try:
        return version("gh-review-dashboard")
    except PackageNotFoundError:
        return "dev"


class InstallMethod(Enum):
    UV_TOOL = "uv_tool"
    PIPX = "pipx"
    PIP = "pip"


def detect_install_method() -> InstallMethod:
    """Detect how gh-review-dashboard was installed."""
    # Try uv tool list
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "gh-review-dashboard" in result.stdout:
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
        if "gh-review-dashboard" in result.stdout:
            return InstallMethod.PIPX
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return InstallMethod.PIP


def run_upgrade(method: InstallMethod | None = None) -> None:
    """Run the appropriate upgrade command for the detected install method."""
    if method is None:
        method = detect_install_method()

    commands: dict[InstallMethod, list[str]] = {
        InstallMethod.UV_TOOL: ["uv", "tool", "upgrade", "gh-review-dashboard"],
        InstallMethod.PIPX: ["pipx", "upgrade", "gh-review-dashboard"],
        InstallMethod.PIP: [
            sys.executable, "-m", "pip", "install", "--upgrade", "gh-review-dashboard",
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

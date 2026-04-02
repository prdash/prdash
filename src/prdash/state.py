"""Lightweight UI state persistence (separate from config)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from prdash.config import CONFIG_DIR

STATE_FILE: Path = CONFIG_DIR / "state.json"


def load_state(path: Path | None = None) -> dict:
    """Load UI state from JSON file. Returns empty dict on missing/corrupt."""
    state_path = path or STATE_FILE
    if not state_path.exists():
        return {}
    try:
        with open(state_path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(data: dict, path: Path | None = None) -> None:
    """Save UI state to JSON file atomically."""
    state_path = path or STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, indent=2) + "\n"

    fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent, suffix=".tmp", prefix=".state_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, state_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_collapsed_groups(path: Path | None = None) -> set[str]:
    """Get the set of collapsed group names from state."""
    state = load_state(path)
    collapsed = state.get("collapsed_groups", [])
    if not isinstance(collapsed, list):
        return set()
    return set(collapsed)


def set_collapsed_groups(groups: set[str], path: Path | None = None) -> None:
    """Save the set of collapsed group names to state."""
    state = load_state(path)
    state["collapsed_groups"] = sorted(groups)
    save_state(state, path)

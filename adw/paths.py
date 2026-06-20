"""Path resolution: where the engine lives vs. which repo it operates on.

The harness has two roots:

- **engine root** — where the installed `adw/` package and its default
  prompt/config assets (`commands/`, `configs/`, `stage_specs/`) live. Fixed
  to wherever this code is installed.
- **target root** — the repo the harness actually *operates on*: its
  `prd.json`, `state.json`, run logs, git branch/commits, and `.claude/`
  hooks. Resolved from `ADW_REPO`, else the git top-level of the current
  directory, else the engine itself.

Self-hosting (S-001..S-010): with `ADW_REPO` unset and the process running
inside this repo, the target resolves to the engine, so every path is
exactly what it was before this module existed. Pointing `ADW_REPO` at
another repo makes the harness build *that* repo instead, with zero code
copied — the target only needs a small `.adw/` skeleton (see
`docs/using-on-another-repo.md`). Per-project asset overrides live under the
target's `.adw/` (`.adw/commands`, `.adw/configs`) and win over the engine's.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

ADW_REPO_ENV = "ADW_REPO"


def engine_root() -> Path:
    """The installed engine: where adw/, commands/, configs/, stage_specs/ live."""
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def target_root() -> Path:
    """The repo the harness operates on: ADW_REPO, else the git top-level of
    cwd, else the engine (self-hosting).

    Memoized for the process; tests that change ADW_REPO must call
    `target_root.cache_clear()` to re-resolve.
    """
    env = os.environ.get(ADW_REPO_ENV)
    if env:
        return Path(env).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return Path(out).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return engine_root()


def _asset_dir(name: str) -> Path:
    """A prompt/config asset directory: the target's `.adw/<name>` override if
    it exists, else the engine's `<name>`."""
    override = target_root() / ".adw" / name
    if override.is_dir():
        return override
    return engine_root() / name


# --- Asset locations (engine, or per-project .adw/ override) ----------------

def commands_dir() -> Path:
    return _asset_dir("commands")


def configs_dir() -> Path:
    return _asset_dir("configs")


def stage_specs_dir() -> Path:
    return _asset_dir("stage_specs")


def models_path() -> Path:
    return configs_dir() / "models.json"


def budgets_path() -> Path:
    return configs_dir() / "budgets.json"


# --- Target-repo state locations (always the target) ------------------------

def prd_path() -> Path:
    return target_root() / "prd.json"


def state_path() -> Path:
    return target_root() / "state.json"


def runs_root() -> Path:
    return target_root() / "observability" / "runs"


def history_path() -> Path:
    return target_root() / "observability" / "history.md"

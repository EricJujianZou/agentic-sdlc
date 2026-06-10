#!/usr/bin/env python3
"""PostToolUse auto-commit: micro-commit per file edit (plans/hooks_plan.md §3).

Stdin: hook JSON ({tool_name, tool_input, cwd, ...}). Gives fine-grained
revert points during a run; the stage-boundary squash into one well-named
commit is the workflow's job (deferred in v1). Adapted from
rinadelph/rins_hooks auto-commit.

Only active during harness-driven runs (ADW_TICKET_RUN=1) — auto-commits
in attended sessions would be noise. Never blocks: always exits 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if not os.environ.get("ADW_TICKET_RUN"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw_path:
        return 0
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        rel = Path(raw_path).resolve().relative_to(Path(cwd).resolve()).as_posix()
    except ValueError:
        return 0  # outside the project; nothing to commit

    tool = payload.get("tool_name", "edit").lower()
    try:
        subprocess.run(["git", "add", "--", rel], cwd=cwd, capture_output=True, timeout=30)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=cwd, capture_output=True, timeout=30
        )
        if staged.returncode != 0:  # something is staged
            subprocess.run(
                ["git", "commit", "-m", f"adw auto: {tool} {rel}"],
                cwd=cwd, capture_output=True, timeout=60,
            )
    except (OSError, subprocess.SubprocessError):
        pass  # auto-commit is best-effort; a failure must not break the run
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Stop-hook checklist: a stage is not complete until this passes (plans/hooks_plan.md §2).

Stdin: hook JSON ({transcript_path, stop_hook_active, cwd, ...}). Exit 0
accepts the stop; exit 2 rejects it and feeds the stderr checklist back to
the agent, which must fix the items and try again.

Only active during harness-driven runs (ADW_TICKET_RUN=1, set by
adw/invoke.py). Checks, per the plan:
- the last assistant message ends with a parseable status block
- the working tree is clean (everything committed)
- progress.txt is within its line cap

Failed checklist = stage not complete, regardless of what the agent said.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# adw is imported from this script's repo, not the target project, so the
# checklist works even when the harness runs against another codebase.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw.progress import ProgressCapExceeded, assert_under_cap
from adw.status import StatusBlockError, parse_status_block


def last_assistant_text(transcript_path: str) -> str:
    """Concatenated text blocks of the last assistant message in the JSONL transcript."""
    text = ""
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content", "")
        if isinstance(content, str):
            candidate = content
        else:
            candidate = "\n".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if candidate.strip():
            text = candidate
    return text


def working_tree_dirty(cwd: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd or None, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # not a git repo / git unavailable: don't block on it
    dirty = proc.stdout.strip()
    return dirty if dirty else None


def main() -> int:
    if not os.environ.get("ADW_TICKET_RUN"):
        return 0  # attended session: stop freely
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):
        return 0  # already continuing because of this hook; never loop forever

    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    failures: list[str] = []

    transcript = payload.get("transcript_path", "")
    text = last_assistant_text(transcript) if transcript else ""
    if text:
        try:
            parse_status_block(text)
        except StatusBlockError as exc:
            failures.append(
                f"status block missing/invalid ({exc}); end your reply with the JSON "
                "status block from plans/harness_plan.md §2"
            )

    # Read-only stages (plan, review) have no git-write tools, so a dirty
    # tree is the orchestrator's bookkeeping, not their unfinished work —
    # demanding a commit they cannot make would deadlock the stage.
    if os.environ.get("ADW_STAGE") not in ("plan", "review"):
        dirty = working_tree_dirty(cwd)
        if dirty is not None:
            files = ", ".join(line.split()[-1] for line in dirty.splitlines()[:5])
            failures.append(f"working tree not clean — commit your work first ({files})")

    try:
        assert_under_cap(Path(cwd) / "progress.txt")
    except ProgressCapExceeded as exc:
        failures.append(str(exc))

    if failures:
        print("stage incomplete:\n- " + "\n- ".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""PreToolUse guard: deny-rules enforced at the tool-call level (plans/hooks_plan.md §1).

Stdin: hook JSON ({tool_name, tool_input, cwd, ...}). Exit 0 allows the
call; exit 2 denies it and feeds the one-line stderr reason back to the
agent so it can adjust instead of flailing. Adapted from the exit-code
convention in rohitg00/awesome-claude-code-toolkit hooks.

Always enforced (attended or not): destructive git commands, push/merge
to main, --no-verify, rm -rf outside the worktree.

Enforced only during harness-driven runs (ADW_TICKET_RUN=1, set by
adw/invoke.py): edits to harness files require the current ticket to be
an approved system-repair story (plans/tickets_plan.md §5).

Note: a denial here surfaces to the agent as a failed tool call, not as a
CLI permission_denial; repeated retries trip the circuit breaker via its
same-error / no-change counters instead (adw/safety.py).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

DESTRUCTIVE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgit\s+push\b[^|;&]*(\s--force\b|\s-f\b)"),
     "force push is blocked: history on shared branches is immutable"),
    (re.compile(r"\bgit\s+push\b[^|;&]*\b(main|master)\b"),
     "pushing to main is blocked: merge to main is a human-only gate (plans/safety_plan.md §4)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "git reset --hard is blocked: use git checkout -- <file> or a revert commit"),
    (re.compile(r"\bgit\s+(filter-branch|rebase)\b|\bgit\s+commit\b[^|;&]*--amend\b"),
     "history rewrites (rebase/amend/filter-branch) are blocked: make a new commit"),
    (re.compile(r"--no-verify\b"),
     "--no-verify is blocked: pre-commit hooks are part of the deterministic harness"),
]

RM_RF = re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[a-zA-Z]*\b")
UNSAFE_PATH = re.compile(r"^(/|~|[A-Za-z]:)|(^|/)\.\.(/|$)")

# Directories whose contents are the harness itself; agents may only touch
# them on an approved system-repair ticket (plans/hooks_plan.md §1).
HARNESS_DIRS = (
    "adw", "hooks", "workflows", "stage_specs", "skills", "commands",
    "configs", "plans", ".claude",
)


def deny(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def current_branch(cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd or None, capture_output=True, text=True, timeout=10,
        )
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_command(command: str, cwd: str) -> None:
    for pattern, reason in DESTRUCTIVE_RULES:
        if pattern.search(command):
            deny(reason)
    if RM_RF.search(command):
        for token in command.split():
            if UNSAFE_PATH.search(token.strip("'\"")):
                deny("recursive force delete outside the worktree is blocked")
    if re.search(r"\bgit\s+(push|merge)\b", command) and current_branch(cwd) in ("main", "master"):
        deny("push/merge while on main is blocked: agents work on adw/<ticket-id> branches")


def _story_type(project_dir: Path, ticket_id: str) -> str | None:
    """The `type` of story `ticket_id`, from its sharded `prd/<id>.json` shard
    (GH-79), falling back to a legacy single-file `prd.json`."""
    shard = project_dir / "prd" / f"{ticket_id}.json"
    if shard.exists():
        try:
            return json.loads(shard.read_text(encoding="utf-8")).get("type")
        except (OSError, json.JSONDecodeError):
            return None
    try:
        prd = json.loads((project_dir / "prd.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for story in prd.get("stories", []):
        if story.get("id") == ticket_id:
            return story.get("type")
    return None


def is_system_repair_run(project_dir: Path) -> bool:
    """True when the active ticket (state.json) is a system-repair story."""
    try:
        state = json.loads((project_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return _story_type(project_dir, state.get("ticket_id")) == "system-repair"


def check_file_edit(tool_input: dict, project_dir: Path) -> None:
    if not os.environ.get("ADW_TICKET_RUN"):
        return  # attended session: humans may edit the harness freely
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw_path:
        return
    try:
        rel = Path(raw_path).resolve().relative_to(project_dir.resolve())
    except ValueError:
        return  # outside the project; not a harness file
    if rel.parts and rel.parts[0] in HARNESS_DIRS and not is_system_repair_run(project_dir):
        deny(
            f"editing harness file {rel.as_posix()} is blocked during a normal ticket "
            "run: file a system-repair ticket instead (plans/tickets_plan.md §5)"
        )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # malformed input never blocks; the harness stays out of the way
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    if tool_name in ("Bash", "PowerShell"):
        check_command(tool_input.get("command", ""), cwd)
    elif tool_name in ("Edit", "Write", "NotebookEdit"):
        check_file_edit(tool_input, Path(cwd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

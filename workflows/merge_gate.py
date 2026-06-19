"""Merge-gate finalizer: a human runs this after merging adw/<ticket-id> into main.

Usage: uv run python workflows/merge_gate.py --ticket S-001 --summary "what + why"

Closes audit finding A1 (plans/improvements.md): the durable record gets
its one line in observability/history.md and the ticket's run logs under
observability/runs/<id>/ are deleted (they are hand-offs within one run,
plans/harness_plan.md §5 — append-forever artifacts are bugs).

Deterministic and human-run: merging to main is the one step the harness
never performs, so this finalizer is invoked manually, not by workflows.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# REPO_ROOT here is the ENGINE root, used only to import the adw package; the
# repo being finalized is the *target* (adw/paths.py).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw import paths, runlog
from adw.tickets import get_story, load_prd


class MergeGateError(RuntimeError):
    """The ticket is not in a finalizable state; the message says why."""


def finalize(
    ticket_id: str,
    summary: str,
    *,
    prd_path: str | Path | None = None,
    history_path: str | Path | None = None,
    runs_root: str | Path | None = None,
    force: bool = False,
) -> list[str]:
    """Append the history line and delete run logs for a merged ticket.

    Idempotent: an existing history line for the ticket is never duplicated,
    and cleanup of already-deleted run logs is a no-op. Returns the list of
    actions taken, for the caller to print. Paths default to the target repo
    (adw/paths.py); tests pass them explicitly.
    """
    prd_path = paths.prd_path() if prd_path is None else prd_path
    history_path = paths.history_path() if history_path is None else history_path
    runs_root = paths.runs_root() if runs_root is None else runs_root
    prd = load_prd(prd_path)
    try:
        story = get_story(prd, ticket_id)
    except KeyError as exc:
        raise MergeGateError(str(exc)) from exc
    if not force and not (story.status == "done" and story.passes):
        raise MergeGateError(
            f"{ticket_id} has status={story.status!r} passes={story.passes} — "
            "the gate finalizes only done+passing tickets (--force to override)"
        )

    actions: list[str] = []
    history_file = Path(history_path)
    history_text = history_file.read_text(encoding="utf-8") if history_file.exists() else ""
    line_pattern = rf"^- \d{{4}}-\d{{2}}-\d{{2}} {re.escape(ticket_id)}:"
    if re.search(line_pattern, history_text, re.MULTILINE):
        actions.append(f"history line for {ticket_id} already present; not appending")
    else:
        runlog.append_history_line(ticket_id, summary, history_path)
        actions.append(f"appended history line for {ticket_id}")

    run_logs = Path(runs_root) / ticket_id
    if run_logs.exists():
        runlog.cleanup_run(ticket_id, runs_root)
        actions.append(f"deleted run logs {run_logs}")
    else:
        actions.append("no run logs to delete")
    return actions


def _branch_merged_into_main(branch: str) -> bool | None:
    """True/False whether a local branch is an ancestor of main; None if the
    branch no longer exists (already deleted after merge)."""
    exists = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=paths.target_root(), capture_output=True,
    ).returncode == 0
    if not exists:
        return None
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"],
        cwd=paths.target_root(), capture_output=True,
    ).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", required=True, help="story id, e.g. S-001")
    parser.add_argument(
        "--summary", required=True,
        help="one line of what + why for observability/history.md",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="finalize even if the ticket is not done+passing or the branch is unmerged",
    )
    args = parser.parse_args()

    merged = _branch_merged_into_main(f"adw/{args.ticket}")
    if merged is False and not args.force:
        print(f"refusing: branch adw/{args.ticket} exists but is not merged into main")
        print("merge it first (human-only), or pass --force if you know better")
        return 1

    try:
        actions = finalize(args.ticket, args.summary, force=args.force)
    except MergeGateError as exc:
        print(f"refusing: {exc}")
        return 1
    for action in actions:
        print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

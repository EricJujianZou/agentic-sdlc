"""One-shot intake-to-backlog runner: pull phone-filed tickets, then work them.

Usage: uv run python workflows/poll_once.py [--max-tickets N] [--max-iterations N]

One pass = one launch (S-012). It runs `sync_issues` to ingest open GitHub
issues labeled `adw` into prd.json, then `run_backlog` over the open stories —
honoring the circuit-breaker cooldown between tickets and the --max-tickets
bound, stopping (never skipping) on the first blocked/halted outcome.

Deliberately NOT a daemon: there is no loop, timer, or background thread here.
If you want periodic pickup, point an OS scheduler (Windows Task Scheduler or
cron) at this command on an always-on machine — that wiring is a human opt-in,
outside the harness's authority (see README "Phone-facing backlog").

A sync failure (offline / no credential) stops BEFORE the backlog: the pass
never runs tickets on a stale or partial sync.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent  # engine root, for imports
sys.path.insert(0, str(REPO_ROOT))

from adw.github import GitHubError
from adw.workflow_runner import BacklogResult
from workflows.run_backlog import DEFAULT_MAX_TICKETS, run_backlog
from workflows.sync_issues import pull_and_sync

# sync_fn() -> (ok, message); backlog_fn() -> BacklogResult. Injected so the
# pass is testable without live GitHub or real workflows.
SyncFn = Callable[[], "tuple[bool, str]"]
BacklogFn = Callable[[], BacklogResult]


@dataclass
class PollResult:
    synced: bool
    sync_message: str
    backlog: BacklogResult | None  # None when sync failed (backlog never ran)

    def exit_code(self) -> int:
        if not self.synced:
            return 1
        return 0 if (self.backlog is not None and self.backlog.clean) else 1


def poll_once(*, sync_fn: SyncFn, backlog_fn: BacklogFn) -> PollResult:
    """One pass: sync, then (only if sync succeeded) work the backlog. A failed
    sync short-circuits — the backlog never runs on a stale/partial sync."""
    ok, message = sync_fn()
    if not ok:
        return PollResult(synced=False, sync_message=message, backlog=None)
    return PollResult(synced=True, sync_message=message, backlog=backlog_fn())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-tickets", type=int, default=DEFAULT_MAX_TICKETS,
        help=f"upper bound on tickets worked this pass (default {DEFAULT_MAX_TICKETS})",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="per-ticket plan->review cap (default from budgets.json)",
    )
    args = parser.parse_args()

    def sync_fn() -> tuple[bool, str]:
        try:
            added, skipped = pull_and_sync()
        except GitHubError as exc:
            return False, f"sync failed (offline or no credential?): {exc}"
        return True, f"synced: +{len(added)} new story(ies), {len(skipped)} skipped"

    def backlog_fn() -> BacklogResult:
        return run_backlog(args.max_tickets, args.max_iterations)

    result = poll_once(sync_fn=sync_fn, backlog_fn=backlog_fn)
    print(result.sync_message)
    if result.backlog is None:
        print("stopping before backlog — not running tickets on a stale/partial sync")
    else:
        b = result.backlog
        print(f"backlog: ran {b.tickets_run} ticket(s); {b.stop_reason}")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

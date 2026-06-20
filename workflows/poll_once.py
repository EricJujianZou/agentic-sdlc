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
import datetime as _dt
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent  # engine root, for imports
sys.path.insert(0, str(REPO_ROOT))

from adw import paths
from adw.github import GitHubError
from adw.locks import DEFAULT_STALE_SECONDS, LockHeld, single_flight
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


# --- self-logging (S-020) ---------------------------------------------------
# A scheduled poll pass is invisible after the fact unless it records what it
# did, and a shell-redirect on the registered task is fragile (the live \ADW\
# task was registered without one). So poll_once self-logs: one bounded,
# timestamped summary line per pass to a file OUTSIDE the repo, regardless of
# how the task is registered. The log dirties no tracked tree, and any failure
# to write it is swallowed so logging can never affect the pass.

_LOG_FIELD_CAP = 300  # keep each variable segment bounded -> one tidy line


def default_log_path() -> Path:
    """Where to append the poll log. `ADW_POLL_LOG` overrides; else
    %LOCALAPPDATA%/adw/poll.log on Windows, ~/.adw/poll.log elsewhere — always
    outside the repo so an unattended run never dirties the working tree."""
    env = os.environ.get("ADW_POLL_LOG")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "adw" / "poll.log"
    return Path.home() / ".adw" / "poll.log"


def poll_lock_path() -> Path:
    """Where the single-flight lock for THIS target repo lives (S — race-safety).
    Keyed by the target path so polls against different repos (the engine vs a
    cross-repo target) never block each other, and always outside the repo so it
    never dirties the tree. `ADW_POLL_LOCK` overrides the full path."""
    env = os.environ.get("ADW_POLL_LOCK")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "adw" if base else Path.home() / ".adw"
    key = hashlib.sha1(str(paths.target_root()).encode("utf-8")).hexdigest()[:12]
    return root / "locks" / f"poll-{key}.lock"


def _stale_seconds_from_env() -> float:
    """Lock staleness override: `ADW_POLL_LOCK_STALE_MINUTES`, else the default."""
    raw = os.environ.get("ADW_POLL_LOCK_STALE_MINUTES")
    if raw:
        try:
            return float(raw) * 60
        except ValueError:
            pass
    return DEFAULT_STALE_SECONDS


def _clip(text: str) -> str:
    text = " ".join(text.split())  # collapse newlines so one pass == one line
    return text if len(text) <= _LOG_FIELD_CAP else text[: _LOG_FIELD_CAP - 1] + "…"


def format_summary_line(
    result: PollResult, *, started_at: _dt.datetime, finished_at: _dt.datetime
) -> str:
    """One bounded summary line for a pass: start time, elapsed seconds, sync
    outcome, and either the backlog result (tickets run + stop reason) or the
    stop-before-backlog note. Elapsed seconds make a long pass self-explaining
    (the 29-min mystery run that prompted S-020 left no such trace)."""
    elapsed = max(0.0, (finished_at - started_at).total_seconds())
    started = started_at.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if result.backlog is None:
        tail = "backlog skipped (stale/partial sync — tickets not run)"
    else:
        b = result.backlog
        tail = f"ran {b.tickets_run} ticket(s); {_clip(b.stop_reason)}"
    return (
        f"{started} | {elapsed:.1f}s | sync: {_clip(result.sync_message)} | {tail}"
    )


def append_log(log_path: str | Path, line: str) -> None:
    """Append one line to the poll log, creating parent dirs as needed. Any
    failure is swallowed — logging must never affect the pass outcome."""
    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


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
    parser.add_argument(
        "--log-path", default=None,
        help="append a per-pass summary line here (default: $ADW_POLL_LOG or "
             "%LOCALAPPDATA%/adw/poll.log); always outside the repo",
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

    log_path = Path(args.log_path) if args.log_path else default_log_path()
    started_at = _dt.datetime.now(_dt.timezone.utc)
    # Single-flight: if another pass already holds this repo's lock, skip cleanly
    # rather than double-running. A manual trigger and the scheduled \ADW\ task
    # would otherwise interleave their prd.json read-modify-write and collide on
    # the git work branch. Skipping is expected contention, not an error (exit 0).
    try:
        with single_flight(poll_lock_path(), stale_seconds=_stale_seconds_from_env()):
            result = poll_once(sync_fn=sync_fn, backlog_fn=backlog_fn)
    except LockHeld as exc:
        finished_at = _dt.datetime.now(_dt.timezone.utc)
        elapsed = max(0.0, (finished_at - started_at).total_seconds())
        started = started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        append_log(log_path, f"{started} | {elapsed:.1f}s | skipped: {exc}")
        print(f"skipped: {exc}")
        return 0
    finished_at = _dt.datetime.now(_dt.timezone.utc)

    append_log(
        log_path,
        format_summary_line(result, started_at=started_at, finished_at=finished_at),
    )

    print(result.sync_message)
    if result.backlog is None:
        print("stopping before backlog — not running tickets on a stale/partial sync")
    else:
        b = result.backlog
        print(f"backlog: ran {b.tickets_run} ticket(s); {b.stop_reason}")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

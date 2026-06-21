"""Backlog runner: work the open backlog ticket-by-ticket to completion.

Usage: uv run python workflows/run_backlog.py [--max-tickets N] [--max-iterations N]

A thin outer loop (snarktank/ralph pattern) over adw.workflow_runner: while
open stories remain it picks the next one, dispatches it to the pipeline for
its type, and repeats — honoring the circuit-breaker cooldown between tickets
and stopping (never skipping) on the first blocked/halted outcome. It adds no
new authority; the inner safety model is unchanged. Merge to main stays the
human gate, so every completed ticket leaves a branch awaiting review.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw import paths
from adw.orchestrator import TicketOutcome
from adw.safety import check_cooldown
from adw.tickets import Story
from adw.workflow_runner import (
    BacklogResult,
    STAGE_ORDER_BY_TYPE,
    reap_stale_in_progress,
    run_backlog_loop,
    run_one_story,
    run_parallel_backlog,
)

DEFAULT_MAX_TICKETS = 20


def run_backlog(
    max_tickets: int, max_iterations: int | None = None, *, parallel: bool = False
) -> BacklogResult:
    """Work the open backlog ticket-by-ticket (one pass, bounded by max_tickets).
    Factored out of main() so the one-shot intake runner (workflows/poll_once.py)
    can reuse the exact same per-ticket dispatch and stop conditions.

    With `parallel=True` (opt-in, #4) it instead runs up to budgets.max_parallel
    tickets concurrently, each in its own git worktree, so one blocked ticket
    halts only its worktree rather than the whole backlog. Sequential remains
    the default until parallel is proven; poll_once never passes parallel=True."""
    models = json.loads(paths.models_path().read_text(encoding="utf-8"))
    budgets = json.loads(paths.budgets_path().read_text(encoding="utf-8"))
    max_iterations = max_iterations or budgets["max_iterations_default"]

    if parallel:
        return run_parallel_backlog(
            max_tickets=max_tickets,
            max_iterations=max_iterations,
            max_parallel=budgets.get("max_parallel", 3),
            models=models,
            budgets=budgets,
        )

    def run_story_fn(story: Story) -> TicketOutcome:
        stage_order = STAGE_ORDER_BY_TYPE.get(story.type)
        if stage_order is None:  # defensive: schema restricts type, but never dispatch blind
            return TicketOutcome(story.id, "blocked", reason=f"no workflow for type {story.type!r}")
        return run_one_story(
            story, stage_order, models=models, budgets=budgets, max_iterations=max_iterations
        )

    return run_backlog_loop(
        run_story_fn=run_story_fn,
        cooldown_fn=check_cooldown,
        max_tickets=max_tickets,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-tickets", type=int, default=DEFAULT_MAX_TICKETS,
        help=f"upper bound on tickets this run (default {DEFAULT_MAX_TICKETS})",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="per-ticket plan->review cap (default from budgets.json)",
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="run up to budgets.max_parallel tickets concurrently, each in its own "
        "git worktree (#4, opt-in). A blocked ticket halts only its worktree, not "
        "the backlog. Default is sequential, stop-on-block.",
    )
    args = parser.parse_args()
    result = run_backlog(args.max_tickets, args.max_iterations, parallel=args.parallel)
    print(f"backlog runner: ran {result.tickets_run} ticket(s); {result.stop_reason}")
    return 0 if result.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())

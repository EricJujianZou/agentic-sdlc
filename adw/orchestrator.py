"""The stage loop: the only component with authority (plans/harness_plan.md).

Routes on parsed status blocks only: success -> next stage; failure ->
bounded loop back to plan; blocked -> halt for human. Loop bounds are
enforced here, never by prompts. The full circuit breaker lives in
adw/safety.py (plans/safety_plan.md) and plugs in via `breaker`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from adw import runlog
from adw.invoke import StageResult
from adw.state import State, new_state, save_state
from adw.tickets import Story

STAGE_ORDER = ("plan", "implement", "test", "review")

# invoke_fn(stage, state, story) -> StageResult. Injected so the loop is
# testable without spawning real agents.
InvokeFn = Callable[[str, State, Story], StageResult]


class Breaker(Protocol):
    """Circuit-breaker interface; the real one is adw/safety.py."""

    def record(self, state: State, result: StageResult) -> str | None:
        """Return a halt reason to open the circuit, or None to continue."""
        ...


@dataclass
class TicketOutcome:
    ticket_id: str
    outcome: str  # "done" | "blocked" | "halted"
    reason: str | None = None
    iterations: int = 1
    tokens_used: int = 0
    stages_run: list[str] = field(default_factory=list)


@dataclass
class _NullBreaker:
    def record(self, state: State, result: StageResult) -> str | None:
        return None


def run_ticket(
    story: Story,
    invoke_fn: InvokeFn,
    *,
    state_path: str | Path,
    max_iterations: int = 5,
    breaker: Breaker | None = None,
    runs_root: str | Path = runlog.DEFAULT_RUNS_ROOT,
) -> TicketOutcome:
    """Drive one ticket through plan -> implement -> test -> review.

    Ticket completion is the dual gate (plans/safety_plan.md §1): the review
    stage must report outcome=success AND exit_signal=true (test-stage
    verification of acceptance criteria is part of the test contract).
    """
    breaker = breaker or _NullBreaker()
    state = new_state(story.id)
    save_state(state, state_path)
    stages_run: list[str] = []

    while state.iteration <= max_iterations:
        for stage in STAGE_ORDER:
            state.stage = stage
            save_state(state, state_path)
            result = invoke_fn(stage, state, story)
            state.budget_used_tokens += result.tokens_used
            stages_run.append(stage)
            runlog.write_stage_log(
                story.id,
                stage=stage,
                iteration=state.iteration,
                payload={
                    "stage": stage,
                    "outcome": result.status.outcome if result.status else None,
                    "summary": result.status.summary if result.status else None,
                    "parse_error": result.parse_error,
                    "timed_out": result.timed_out,
                    "tokens_used": result.tokens_used,
                    "exit_code": result.exit_code,
                    "stderr_head": result.stderr[:500],
                },
                runs_root=runs_root,
            )

            # Completion outranks the breaker: the dual gate passing means
            # the ticket is done, and a cumulative counter (e.g. permission
            # denials earlier in the run) must not veto finished work.
            if (
                stage == "review"
                and result.status is not None
                and result.status.outcome == "success"
                and result.status.exit_signal
            ):
                state.last_failure = None
                save_state(state, state_path)
                return _finish(story, state, "done", None, stages_run)

            halt_reason = breaker.record(state, result)
            if halt_reason is not None:
                state.last_failure = halt_reason
                save_state(state, state_path)
                return _finish(story, state, "halted", halt_reason, stages_run)

            if result.status is None:
                # Unparseable output is a stage failure, not a completion.
                state.last_failure = f"{stage}: {result.parse_error or 'no status block'}"
                break
            if result.status.outcome == "blocked":
                reason = result.status.failure_reason or result.status.summary
                state.last_failure = reason
                save_state(state, state_path)
                return _finish(story, state, "blocked", reason, stages_run)
            if result.status.outcome == "failure":
                state.last_failure = result.status.failure_reason or f"{stage} failed"
                break
            # success (review success WITH exit_signal already returned above)
            state.last_failure = None
            if stage == "review":
                # Review succeeded but did not assert completion — loop.
                state.last_failure = "review success without exit_signal"
                break
        else:
            continue  # unreachable: review always breaks or returns
        state.iteration += 1
        save_state(state, state_path)

    reason = f"max iterations ({max_iterations}) reached; last failure: {state.last_failure}"
    return _finish(story, state, "halted", reason, stages_run)


def _finish(
    story: Story,
    state: State,
    outcome: str,
    reason: str | None,
    stages_run: list[str],
) -> TicketOutcome:
    return TicketOutcome(
        ticket_id=story.id,
        outcome=outcome,
        reason=reason,
        iterations=state.iteration,
        tokens_used=state.budget_used_tokens,
        stages_run=stages_run,
    )

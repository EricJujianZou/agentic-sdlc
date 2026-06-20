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
from adw.safety import USAGE_LIMIT_HALT_REASON
from adw.state import State, new_state, save_state
from adw.status import _candidate_objects
from adw.tickets import Story

STAGE_ORDER = ("plan", "implement", "test", "review")
DOCUMENT_STAGE = "document"
DECOMPOSE_STAGE = "decompose"
OBSERVE_STAGE = "observe"

# invoke_fn(stage, state, story) -> StageResult. Injected so the loop is
# testable without spawning real agents.
InvokeFn = Callable[[str, State, Story], StageResult]

# verify_fn() -> (passed, detail). The orchestrator's own deterministic
# test-evidence re-run after the dual gate passes — NOT a stage agent's
# self-report (improvements C3). Injected so the loop is testable without
# spawning the real suite; defaults to None (no extra check), the same way
# breaker defaults to a no-op.
VerifyFn = Callable[[], "tuple[bool, str]"]

# progress_fn(stage, outcome_label, summary) -> None. Best-effort, side-channel
# notification of stage transitions (S-014) — e.g. a comment on the source
# GitHub issue so the phone gets a running log. `summary` is the stage's own
# one-line self-report from its status block, so the phone sees what each stage
# did, not just a bare outcome. The orchestrator is the only thing that calls
# it; stage agents never touch the outside world. Injected and defaulting to
# None; it must never raise (the caller swallows failures), so a notification
# problem can never change a ticket's outcome.
ProgressFn = Callable[[str, str, str], None]


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
    warning: str | None = None
    test_evidence: str | None = None  # deterministic local pytest count on done


@dataclass
class _NullBreaker:
    def record(self, state: State, result: StageResult) -> str | None:
        return None


def run_ticket(
    story: Story,
    invoke_fn: InvokeFn,
    *,
    stage_order: tuple[str, ...] = STAGE_ORDER,
    state_path: str | Path,
    max_iterations: int = 5,
    breaker: Breaker | None = None,
    verify_fn: VerifyFn | None = None,
    progress_fn: ProgressFn | None = None,
    runs_root: str | Path | None = None,
) -> TicketOutcome:
    """Drive one ticket through its `stage_order` (plan -> implement -> test
    -> review for feat; the bug/trivial workflows pass shorter orders).

    Completion is the success of the gate stage — the last stage in
    `stage_order`. When that gate is the review stage the dual gate applies
    (plans/safety_plan.md §1): review must report outcome=success AND
    exit_signal=true. For orders that end at test (bug/trivial) the test
    stage's success is the gate; there is no exit_signal to assert. Stage
    order is owned by the workflow scripts, never by prompts.
    """
    breaker = breaker or _NullBreaker()
    gate_stage = stage_order[-1]
    require_exit_signal = gate_stage == "review"
    state = new_state(story.id)
    save_state(state, state_path)
    stages_run: list[str] = []

    while state.iteration <= max_iterations:
        for stage in stage_order:
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

            # One progress notification per stage transition (S-014). Bounded:
            # exactly one per stage execution, never per iteration-internal step.
            # The detail line is the most actionable thing the phone can show:
            # the structured failure_reason on a failure/blocked stage (so the
            # phone sees *why*, not just that it failed), else the summary, else
            # the parse error when the stage emitted no status block at all.
            if progress_fn is not None:
                if result.status is not None:
                    outcome_label = result.status.outcome
                    if result.status.outcome in ("failure", "blocked"):
                        detail = result.status.failure_reason or result.status.summary
                    else:
                        detail = result.status.summary
                else:
                    outcome_label = "no-status"
                    detail = result.parse_error or ""
                progress_fn(stage, outcome_label, detail)

            # Completion outranks the breaker: the gate stage passing means
            # the ticket is done, and a cumulative counter (e.g. permission
            # denials earlier in the run) must not veto finished work.
            if (
                stage == gate_stage
                and result.status is not None
                and result.status.outcome == "success"
                and (result.status.exit_signal or not require_exit_signal)
            ):
                state.last_failure = None
                save_state(state, state_path)
                # Deterministic test-evidence gate (improvements C3): the
                # orchestrator re-runs the suite itself before accepting the
                # agents' "done". A red suite blocks the ticket and the
                # document stage never runs — the agents cannot self-certify
                # a failing tree as done.
                test_evidence: str | None = None
                if verify_fn is not None:
                    passed, detail = verify_fn()
                    if not passed:
                        reason = f"test-evidence re-run failed: {detail}"
                        state.last_failure = reason
                        save_state(state, state_path)
                        return _finish(story, state, "blocked", reason, stages_run)
                    # On a green re-run the detail carries the local pass count
                    # (e.g. "209 passed"); surface it so the outcome comment can
                    # report a deterministic number to cross-check against CI.
                    test_evidence = detail or None
                warning = _run_document_stage(
                    story, state, invoke_fn,
                    state_path=state_path,
                    runs_root=runs_root,
                    stages_run=stages_run,
                    breaker=breaker,
                    progress_fn=progress_fn,
                )
                return _finish(
                    story, state, "done", None, stages_run,
                    warning=warning, test_evidence=test_evidence,
                )

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
            # success (gate success WITH exit_signal already returned above)
            state.last_failure = None
            if stage == gate_stage and require_exit_signal:
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
    *,
    warning: str | None = None,
    test_evidence: str | None = None,
) -> TicketOutcome:
    return TicketOutcome(
        ticket_id=story.id,
        outcome=outcome,
        reason=reason,
        iterations=state.iteration,
        tokens_used=state.budget_used_tokens,
        stages_run=stages_run,
        warning=warning,
        test_evidence=test_evidence,
    )


def parse_decompose_criteria(text: str) -> list[str] | None:
    """Extract the acceptance_criteria array the decompose stage emits in its
    status block. Returns the cleaned non-empty list, or None if absent/empty.
    Reuses the same last-object-wins JSON scan the status parser uses."""
    for obj in _candidate_objects(text):
        ac = obj.get("acceptance_criteria")
        if isinstance(ac, list):
            cleaned = [c.strip() for c in ac if isinstance(c, str) and c.strip()]
            if cleaned:
                return cleaned
    return None


def run_decompose(
    story: Story,
    invoke_fn: InvokeFn,
    *,
    state_path: str | Path,
    runs_root: str | Path | None = None,
) -> tuple[list[str] | None, str | None]:
    """Expand a criteria-less ticket into acceptance criteria via the read-only
    decompose stage (S-013). Returns (criteria, problem): the proposed criteria
    on success, else a problem string the caller blocks on. The decompose agent
    only proposes — the caller persists the result to prd.json, never the agent.
    """
    state = State(ticket_id=story.id, stage=DECOMPOSE_STAGE)
    save_state(state, state_path)
    result = invoke_fn(DECOMPOSE_STAGE, state, story)
    runlog.write_stage_log(
        story.id,
        stage=DECOMPOSE_STAGE,
        iteration=state.iteration,
        payload={
            "stage": DECOMPOSE_STAGE,
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
    if result.status is None:
        return None, f"decompose: {result.parse_error or 'no status block'}"
    if result.status.outcome != "success":
        return None, result.status.failure_reason or f"decompose {result.status.outcome}"
    criteria = parse_decompose_criteria(result.raw_output)
    if not criteria:
        return None, "decompose succeeded but emitted no acceptance_criteria"
    return criteria, None


@dataclass
class ObserverResult:
    """Outcome of the read-only observer (self-heal lens)."""
    classification: str | None  # "ticket" | "harness" | None (not analyzed)
    repair: dict | None         # {title, description, evidence}; only for harness
    summary: str                # one-line diagnosis for the phone
    problem: str | None = None  # set if the observer itself failed to analyze


def parse_observer_proposal(text: str) -> tuple[str | None, dict | None]:
    """Extract (classification, repair) from the observer's status block, using
    the same last-object-wins scan as the status parser. classification is
    normalized to 'ticket'/'harness' or None; repair is returned only when the
    block carries it as a dict (harness case)."""
    for obj in _candidate_objects(text):
        if "classification" in obj:
            cls = obj.get("classification")
            cls = cls.strip().lower() if isinstance(cls, str) else None
            if cls not in ("ticket", "harness"):
                cls = None
            repair = obj.get("repair")
            return cls, (repair if isinstance(repair, dict) else None)
    return None, None


def run_observer(
    story: Story,
    invoke_fn: InvokeFn,
    failure_reason: str,
    *,
    state_path: str | Path,
    runs_root: str | Path | None = None,
) -> ObserverResult:
    """Run the read-only observer once on a non-done ticket (self-heal lens).

    Returns its classification and, for a harness-level diagnosis, a proposed
    repair. The observer only proposes — the caller (workflow_runner) decides
    what to surface; the observer never files, edits, or commits anything. The
    ticket's failure reason is threaded in as state.last_failure so the prompt
    carries it.
    """
    state = State(ticket_id=story.id, stage=OBSERVE_STAGE)
    state.last_failure = failure_reason
    save_state(state, state_path)
    result = invoke_fn(OBSERVE_STAGE, state, story)
    runlog.write_stage_log(
        story.id,
        stage=OBSERVE_STAGE,
        iteration=state.iteration,
        payload={
            "stage": OBSERVE_STAGE,
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
    if result.status is None:
        return ObserverResult(None, None, "", problem=result.parse_error or "no status block")
    if result.status.outcome != "success":
        return ObserverResult(
            None, None, result.status.summary,
            problem=result.status.failure_reason or f"observer {result.status.outcome}",
        )
    classification, repair = parse_observer_proposal(result.raw_output)
    return ObserverResult(classification, repair, result.status.summary)


def _run_document_stage(
    story: Story,
    state: State,
    invoke_fn: InvokeFn,
    *,
    state_path: str | Path,
    runs_root: str | Path,
    stages_run: list[str],
    breaker: Breaker,
    progress_fn: ProgressFn | None = None,
) -> str | None:
    """Run the document stage once with one retry. Returns None on success,
    or a warning string if both attempts fail or the breaker fires. Reports
    its outcome through progress_fn too, so the phone log covers every stage —
    document included — not just the plan->review loop."""
    state.stage = DOCUMENT_STAGE
    last_problem: str = "unknown failure"
    for _attempt in (1, 2):
        save_state(state, state_path)
        result = invoke_fn(DOCUMENT_STAGE, state, story)
        state.budget_used_tokens += result.tokens_used
        stages_run.append(DOCUMENT_STAGE)
        runlog.write_stage_log(
            story.id,
            stage=DOCUMENT_STAGE,
            iteration=state.iteration,
            payload={
                "stage": DOCUMENT_STAGE,
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
        save_state(state, state_path)
        halt_reason = breaker.record(state, result)
        if halt_reason is not None:
            if progress_fn is not None:
                progress_fn(DOCUMENT_STAGE, "failure", f"breaker: {halt_reason}")
            return f"document stage warning (breaker): {halt_reason}"
        if result.status is not None and result.status.outcome == "success":
            if progress_fn is not None:
                progress_fn(DOCUMENT_STAGE, "success", result.status.summary)
            return None
        if result.timed_out:
            last_problem = "timed out"
        elif result.status is not None and result.status.failure_reason:
            last_problem = result.status.failure_reason
        else:
            last_problem = result.parse_error or f"outcome={result.status.outcome if result.status else 'no status block'}"
    if progress_fn is not None:
        progress_fn(DOCUMENT_STAGE, "failure", last_problem)
    return f"document stage warning: {last_problem}"

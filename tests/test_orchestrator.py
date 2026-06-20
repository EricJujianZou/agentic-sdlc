from adw.invoke import StageResult
from adw.orchestrator import run_ticket
from adw.safety import USAGE_LIMIT_HALT_REASON
from adw.state import load_state
from adw.status import StatusBlock
from adw.tickets import Story


def story() -> Story:
    return Story(
        id="S-001",
        type="feat",
        priority=1,
        title="t",
        description="d",
        acceptance_criteria=["c"],
    )


def ok(stage: str, *, exit_signal: bool = False) -> StageResult:
    return StageResult(
        status=StatusBlock(stage=stage, ticket_id="S-001", outcome="success",
                           exit_signal=exit_signal),
        exit_code=0,
        tokens_used=100,
    )


def fail(stage: str, reason: str = "tests failed") -> StageResult:
    return StageResult(
        status=StatusBlock(stage=stage, ticket_id="S-001", outcome="failure",
                           failure_reason=reason),
        exit_code=0,
        tokens_used=100,
    )


def run(invoke_fn, tmp_path, **kwargs):
    return run_ticket(
        story(),
        invoke_fn,
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        **kwargs,
    )


def test_happy_path_one_iteration(tmp_path):
    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path)
    assert outcome.outcome == "done"
    assert outcome.stages_run == ["plan", "implement", "test", "review", "document"]
    assert outcome.tokens_used == 500


def test_progress_fn_called_once_per_stage(tmp_path):
    events = []

    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    run(invoke, tmp_path, progress_fn=lambda stage, outcome, summary="": events.append((stage, outcome)))
    # One event per stage, in order — including document, which runs post-gate
    # and is now reported too so the phone log covers every stage.
    assert events == [
        ("plan", "success"), ("implement", "success"),
        ("test", "success"), ("review", "success"), ("document", "success"),
    ]


def test_progress_fn_receives_stage_summary(tmp_path):
    events = []

    def invoke(stage, state, story):
        return StageResult(
            status=StatusBlock(
                stage=stage, ticket_id="S-001", outcome="success",
                exit_signal=(stage == "review"), summary=f"{stage} did its thing",
            ),
            exit_code=0, tokens_used=1,
        )

    run(invoke, tmp_path, progress_fn=lambda s, o, summary="": events.append((s, summary)))
    # Each stage's own one-line summary reaches the notifier verbatim.
    assert ("plan", "plan did its thing") in events
    assert ("review", "review did its thing") in events


def test_progress_fn_forwards_failure_reason(tmp_path):
    events = []

    def invoke(stage, state, story):
        if stage == "implement":
            return StageResult(
                status=StatusBlock(
                    stage="implement", ticket_id="S-001", outcome="failure",
                    summary="tried to add the endpoint",
                    failure_reason="import cycle between adw.foo and adw.bar",
                ),
                exit_code=0, tokens_used=1,
            )
        return ok(stage, exit_signal=(stage == "review"))

    run(invoke, tmp_path, progress_fn=lambda s, o, detail="": events.append((s, o, detail)))
    # A failing stage surfaces the structured failure_reason, not the vaguer
    # summary, so the phone shows the actionable cause.
    assert ("implement", "failure", "import cycle between adw.foo and adw.bar") in events


def test_progress_fn_reports_blocked_outcome(tmp_path):
    events = []

    def invoke(stage, state, story):
        if stage == "test":
            return StageResult(
                status=StatusBlock(stage="test", ticket_id="S-001",
                                   outcome="blocked", failure_reason="x"),
                exit_code=0, tokens_used=10,
            )
        return ok(stage)

    run(invoke, tmp_path, progress_fn=lambda s, o, summary="": events.append((s, o)))
    assert ("test", "blocked") in events
    assert ("review", "success") not in events  # blocked before reaching review


def test_failure_loops_back_to_plan_then_succeeds(tmp_path):
    calls = []

    def invoke(stage, state, story):
        calls.append((state.iteration, stage))
        if state.iteration == 1 and stage == "test":
            return fail(stage)
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path)
    assert outcome.outcome == "done"
    assert outcome.iterations == 2
    assert (1, "test") in calls and (2, "plan") in calls
    assert (1, "review") not in calls


def test_max_iterations_halts(tmp_path):
    def invoke(stage, state, story):
        return fail(stage) if stage == "test" else ok(stage)

    outcome = run(invoke, tmp_path, max_iterations=3)
    assert outcome.outcome == "halted"
    assert "max iterations (3)" in outcome.reason
    assert "tests failed" in outcome.reason


def test_blocked_halts_immediately(tmp_path):
    def invoke(stage, state, story):
        if stage == "implement":
            return StageResult(
                status=StatusBlock(stage=stage, ticket_id="S-001", outcome="blocked",
                                   failure_reason="needs credentials"),
                exit_code=0,
            )
        return ok(stage)

    outcome = run(invoke, tmp_path)
    assert outcome.outcome == "blocked"
    assert outcome.reason == "needs credentials"


def test_review_success_without_exit_signal_loops(tmp_path):
    def invoke(stage, state, story):
        return ok(stage, exit_signal=False)

    outcome = run(invoke, tmp_path, max_iterations=2)
    assert outcome.outcome == "halted"
    assert "review success without exit_signal" in outcome.reason


def test_unparseable_output_is_failure_not_completion(tmp_path):
    def invoke(stage, state, story):
        if stage == "plan":
            return StageResult(status=None, exit_code=0, parse_error="no status block")
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path, max_iterations=1)
    assert outcome.outcome == "halted"
    assert "no status block" in outcome.reason


def test_breaker_halt_reason_wins(tmp_path):
    class TwoDenialBreaker:
        def __init__(self):
            self.count = 0

        def record(self, state, result):
            self.count += 1
            return "circuit open: permission denials" if self.count >= 2 else None

    outcome = run(
        lambda stage, state, story: ok(stage),
        tmp_path,
        breaker=TwoDenialBreaker(),
    )
    assert outcome.outcome == "halted"
    assert "circuit open" in outcome.reason
    assert outcome.stages_run == ["plan", "implement"]


def test_state_persisted_during_run(tmp_path):
    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    run(invoke, tmp_path)
    state = load_state(tmp_path / "state.json")
    assert state.ticket_id == "S-001"
    assert state.stage == "document"
    assert state.budget_used_tokens == 500


def test_successful_review_outranks_breaker(tmp_path):
    """A passing dual gate must complete the ticket even if a cumulative
    breaker counter (e.g. permission denials) would otherwise trip."""

    class DenialBreaker:
        """Counter crosses the line exactly on the (successful) review."""

        def record(self, state, result):
            if result.status is not None and result.status.stage == "review":
                return "circuit open: too many permission denials"
            return None

    def invoke(stage, state, story):
        result = ok(stage, exit_signal=(stage == "review"))
        result.permission_denials = 1
        return result

    outcome = run(invoke, tmp_path, breaker=DenialBreaker())
    assert outcome.outcome == "done"


def test_breaker_still_halts_unfinished_work(tmp_path):
    class AlwaysOpen:
        def record(self, state, result):
            return "circuit open: stop"

    def invoke(stage, state, story):
        return ok(stage)  # no exit_signal anywhere

    outcome = run(invoke, tmp_path, breaker=AlwaysOpen())
    assert outcome.outcome == "halted"
    assert "circuit open" in outcome.reason


def test_breaker_usage_limit_halt_returns_quotad(tmp_path):
    class UsageLimitBreaker:
        def record(self, state, result):
            return USAGE_LIMIT_HALT_REASON

    def invoke(stage, state, story):
        return ok(stage)  # no exit_signal anywhere

    outcome = run(invoke, tmp_path, breaker=UsageLimitBreaker())
    assert outcome.outcome == "quotad"
    assert outcome.reason == USAGE_LIMIT_HALT_REASON


# --- document stage tests ---


def test_document_runs_once_after_dual_gate(tmp_path):
    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path)
    assert outcome.outcome == "done"
    assert outcome.warning is None
    assert outcome.stages_run.count("document") == 1
    assert outcome.stages_run[-1] == "document"


def test_document_not_invoked_when_review_fails(tmp_path):
    def invoke(stage, state, story):
        if stage == "review":
            return fail(stage, reason="review failed")
        return ok(stage)

    outcome = run(invoke, tmp_path, max_iterations=1)
    assert "document" not in outcome.stages_run


def test_document_not_invoked_when_review_loops(tmp_path):
    """Review success without exit_signal should loop, not invoke document."""
    def invoke(stage, state, story):
        return ok(stage, exit_signal=False)

    outcome = run(invoke, tmp_path, max_iterations=2)
    assert outcome.outcome == "halted"
    assert "document" not in outcome.stages_run


def test_document_failure_retried_once_still_done(tmp_path):
    doc_calls = []

    def invoke(stage, state, story):
        if stage == "document":
            doc_calls.append(stage)
            return fail(stage, reason="commit failed")
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path)
    assert outcome.outcome == "done"
    assert outcome.warning is not None and len(outcome.warning) > 0
    assert outcome.stages_run.count("document") == 2


def test_document_breaker_halt_becomes_warning(tmp_path):
    class BreakerOnDocument:
        def record(self, state, result):
            if state.stage == "document":
                return "circuit open: document"
            return None

    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path, breaker=BreakerOnDocument())
    assert outcome.outcome == "done"
    assert outcome.warning is not None
    assert "breaker" in outcome.warning


# --- bug / trivial workflow stage orders (S-004) ---

BUG_STAGE_ORDER = ("plan", "implement", "test")
TRIVIAL_STAGE_ORDER = ("implement", "test")


def test_bug_order_completes_on_test_success_without_review(tmp_path):
    seen = []

    def invoke(stage, state, story):
        seen.append(stage)
        return ok(stage)  # no exit_signal anywhere; test success is the gate

    outcome = run(invoke, tmp_path, stage_order=BUG_STAGE_ORDER)
    assert outcome.outcome == "done"
    assert "review" not in seen
    assert seen[:3] == ["plan", "implement", "test"]
    assert outcome.stages_run[-1] == "document"  # doc stage still runs post-gate


def test_trivial_order_runs_implement_then_test(tmp_path):
    seen = []

    def invoke(stage, state, story):
        seen.append(stage)
        return ok(stage)

    outcome = run(invoke, tmp_path, stage_order=TRIVIAL_STAGE_ORDER)
    assert outcome.outcome == "done"
    assert seen[:2] == ["implement", "test"]
    assert "plan" not in seen and "review" not in seen


def test_bug_order_test_failure_loops_back_to_plan(tmp_path):
    calls = []

    def invoke(stage, state, story):
        calls.append((state.iteration, stage))
        if state.iteration == 1 and stage == "test":
            return fail(stage)
        return ok(stage)

    outcome = run(invoke, tmp_path, stage_order=BUG_STAGE_ORDER)
    assert outcome.outcome == "done"
    assert (2, "plan") in calls


def test_trivial_order_test_failure_loops_back_to_implement(tmp_path):
    calls = []

    def invoke(stage, state, story):
        calls.append((state.iteration, stage))
        if state.iteration == 1 and stage == "test":
            return fail(stage)
        return ok(stage)

    outcome = run(invoke, tmp_path, stage_order=TRIVIAL_STAGE_ORDER)
    assert outcome.outcome == "done"
    assert (2, "implement") in calls
    assert "plan" not in [stage for _, stage in calls]


# --- deterministic test-evidence gate (S-010) ---


def test_test_evidence_green_completes(tmp_path):
    calls = []

    def verify():
        calls.append("verify")
        return True, ""

    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path, verify_fn=verify)
    assert outcome.outcome == "done"
    assert calls == ["verify"]  # ran exactly once, after the gate
    assert "document" in outcome.stages_run


def test_test_evidence_red_blocks_done_and_skips_document(tmp_path):
    def verify():
        return False, "1 failed, 130 passed"

    def invoke(stage, state, story):
        return ok(stage, exit_signal=(stage == "review"))

    outcome = run(invoke, tmp_path, verify_fn=verify)
    assert outcome.outcome == "blocked"
    assert "1 failed" in outcome.reason
    assert "document" not in outcome.stages_run
    state = load_state(tmp_path / "state.json")
    assert "1 failed" in state.last_failure


def test_test_evidence_not_run_until_completion(tmp_path):
    calls = []

    def verify():
        calls.append("verify")
        return True, ""

    def invoke(stage, state, story):
        return ok(stage)  # no exit_signal anywhere -> never completes

    outcome = run(invoke, tmp_path, verify_fn=verify, max_iterations=1)
    assert outcome.outcome == "halted"
    assert calls == []  # never reached the gate, so never re-ran the suite

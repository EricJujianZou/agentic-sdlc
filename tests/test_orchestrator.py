from adw.invoke import StageResult
from adw.orchestrator import run_ticket
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
    assert outcome.stages_run == ["plan", "implement", "test", "review"]
    assert outcome.tokens_used == 400


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
    assert state.stage == "review"
    assert state.budget_used_tokens == 400

import datetime

from adw.invoke import StageResult, _parse_envelope
from adw.orchestrator import run_ticket
from adw.safety import (
    CircuitBreaker,
    SafetyConfig,
    check_cooldown,
    cooldown_remaining,
    detect_usage_limit,
)
from adw.state import State, load_state, new_state, save_state
from adw.status import StatusBlock
from adw.tickets import Story


def state(stage: str = "implement") -> State:
    s = new_state("S-001")
    s.stage = stage
    return s


def result(
    stage: str = "implement",
    *,
    outcome: str = "success",
    files_changed: int = 0,
    failure_reason: str | None = None,
    raw_output: str = "x" * 3000,
    permission_denials: int = 0,
    parsed: bool = True,
    parse_error: str | None = None,
) -> StageResult:
    status = (
        StatusBlock(stage=stage, ticket_id="S-001", outcome=outcome,
                    failure_reason=failure_reason, files_changed=files_changed)
        if parsed
        else None
    )
    return StageResult(
        status=status,
        exit_code=0,
        raw_output=raw_output,
        permission_denials=permission_denials,
        parse_error=parse_error,
    )


def test_no_change_implement_loops_open_circuit():
    breaker = CircuitBreaker()
    s = state("implement")
    assert breaker.record(s, result(files_changed=0)) is None
    assert breaker.record(s, result(files_changed=0)) is None
    reason = breaker.record(s, result(files_changed=0))
    assert reason is not None and "no file changes" in reason
    assert s.cooldown_until is not None


def test_file_change_resets_no_change_streak():
    breaker = CircuitBreaker()
    s = state("implement")
    breaker.record(s, result(files_changed=0))
    breaker.record(s, result(files_changed=0))
    breaker.record(s, result(files_changed=4))
    assert breaker.record(s, result(files_changed=0)) is None


def test_zero_changes_outside_implement_do_not_count():
    breaker = CircuitBreaker()
    for stage in ("plan", "test", "review", "plan", "test", "review"):
        assert breaker.record(state(stage), result(stage, files_changed=0)) is None


def test_same_error_five_times_opens_circuit():
    breaker = CircuitBreaker()
    s = state("test")
    for _ in range(4):
        assert breaker.record(
            s, result("test", outcome="failure", failure_reason="assert x == 1")
        ) is None
    reason = breaker.record(
        s, result("test", outcome="failure", failure_reason="assert x == 1")
    )
    assert reason is not None and "same error 5 times" in reason


def test_different_error_resets_streak():
    breaker = CircuitBreaker()
    s = state("test")
    for _ in range(4):
        breaker.record(s, result("test", outcome="failure", failure_reason="error A"))
    assert breaker.record(
        s, result("test", outcome="failure", failure_reason="error B")
    ) is None


def test_unparseable_output_counts_as_same_error():
    breaker = CircuitBreaker()
    s = state("plan")
    for _ in range(4):
        assert breaker.record(
            s, result("plan", parsed=False, parse_error="no status block")
        ) is None
    reason = breaker.record(s, result("plan", parsed=False, parse_error="no status block"))
    assert reason is not None and "same error" in reason


def test_output_decline_over_70_pct_opens_circuit():
    breaker = CircuitBreaker()
    s = state("implement")
    assert breaker.record(s, result(files_changed=1, raw_output="x" * 10000)) is None
    reason = breaker.record(s, result(files_changed=1, raw_output="x" * 1000))
    assert reason is not None and "declined" in reason


def test_output_decline_ignores_small_baselines():
    breaker = CircuitBreaker(SafetyConfig(output_decline_floor_chars=1500))
    s = state("review")
    breaker.record(s, result("review", raw_output="x" * 400))
    assert breaker.record(s, result("review", raw_output="x" * 20)) is None


def test_output_decline_compares_within_same_stage():
    breaker = CircuitBreaker()
    # A long implement output followed by a short plan output is normal.
    breaker.record(state("implement"), result("implement", files_changed=1,
                                              raw_output="x" * 10000))
    assert breaker.record(state("plan"), result("plan", raw_output="x" * 100)) is None


def test_permission_denials_accumulate_to_threshold():
    breaker = CircuitBreaker()
    s = state("implement")
    assert breaker.record(s, result(files_changed=1, permission_denials=1)) is None
    reason = breaker.record(s, result(files_changed=1, permission_denials=1))
    assert reason is not None and "permission denials" in reason


def test_token_budget_exceeded_opens_circuit():
    breaker = CircuitBreaker(SafetyConfig(per_ticket_token_budget=1000))
    s = state("implement")
    s.budget_used_tokens = 1001
    reason = breaker.record(s, result(files_changed=1))
    assert reason is not None and "token budget exceeded" in reason


def test_usage_limit_detection():
    assert detect_usage_limit("Claude AI usage limit reached|1718000000")
    assert detect_usage_limit("You have hit your 5-hour limit, try again later")
    assert detect_usage_limit("You're out of extra usage · resets 9pm")
    assert detect_usage_limit(
        '{"rate_limit_event": {"info": "x", "status": "rejected"}}'
    )
    assert not detect_usage_limit("all tests passed, no limits in sight")


def test_usage_limit_halts_immediately():
    breaker = CircuitBreaker()
    reason = breaker.record(
        state("plan"), result("plan", raw_output="usage limit reached")
    )
    assert reason is not None and "usage limit" in reason


def test_config_from_budgets(tmp_path):
    budgets = tmp_path / "budgets.json"
    budgets.write_text(
        '{"per_ticket_token_budget": 5000, "circuit_cooldown_minutes": 45}',
        encoding="utf-8",
    )
    cfg = SafetyConfig.from_budgets(budgets)
    assert cfg.per_ticket_token_budget == 5000
    assert cfg.cooldown_minutes == 45
    assert cfg.no_change_loops == 3  # defaults untouched


def test_cooldown_remaining_and_check(tmp_path):
    s = new_state("S-001")
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    s.cooldown_until = future.isoformat()
    s.last_failure = "circuit open: test"
    assert cooldown_remaining(s) is not None
    save_state(s, tmp_path / "state.json")
    msg = check_cooldown(tmp_path / "state.json")
    assert msg is not None and "cooldown active" in msg and "circuit open: test" in msg


def test_expired_cooldown_does_not_block(tmp_path):
    s = new_state("S-001")
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    s.cooldown_until = past.isoformat()
    save_state(s, tmp_path / "state.json")
    assert check_cooldown(tmp_path / "state.json") is None


def test_missing_state_does_not_block(tmp_path):
    assert check_cooldown(tmp_path / "state.json") is None


def test_breaker_wired_through_run_ticket_persists_cooldown(tmp_path):
    story = Story(id="S-001", type="feat", priority=1, title="t", description="d",
                  acceptance_criteria=["c"])

    def invoke(stage, state, story):
        # implement never changes files; test always fails -> loops forever
        # until the no-change streak opens the circuit on iteration 3.
        if stage == "test":
            return result("test", outcome="failure", failure_reason="boom")
        return result(stage, outcome="success", files_changed=0)

    outcome = run_ticket(
        story,
        invoke,
        state_path=tmp_path / "state.json",
        max_iterations=10,
        breaker=CircuitBreaker(),
        runs_root=tmp_path / "runs",
    )
    assert outcome.outcome == "halted"
    assert "no file changes" in outcome.reason
    persisted = load_state(tmp_path / "state.json")
    assert persisted.cooldown_until is not None
    assert check_cooldown(tmp_path / "state.json") is not None


def test_envelope_permission_denials_parsed():
    envelope = (
        '{"result": "ok", "usage": {"input_tokens": 5, "output_tokens": 7}, '
        '"session_id": "abc", '
        '"permission_denials": [{"tool_name": "Bash"}, {"tool_name": "Write"}]}'
    )
    text, tokens, cost, session_id, denials = _parse_envelope(envelope)
    assert denials == 2
    assert tokens == 12

    _, _, _, _, none_denials = _parse_envelope('{"result": "ok"}')
    assert none_denials == 0

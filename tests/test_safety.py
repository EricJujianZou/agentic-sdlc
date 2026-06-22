import datetime
from zoneinfo import ZoneInfo

from adw.invoke import StageResult, _parse_envelope
from adw.orchestrator import run_ticket
from adw.safety import (
    USAGE_LIMIT_HALT_REASON,
    CircuitBreaker,
    SafetyConfig,
    _parse_usage_reset,
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


def doa_result(stage: str = "plan") -> StageResult:
    """A dead-on-arrival result: non-zero exit, 0 tokens, no output."""
    return StageResult(
        status=None,
        exit_code=1,
        tokens_used=0,
        raw_output="",
        parse_error="no status block",
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


def test_instant_failure_trips_after_two_dead_on_arrival():
    breaker = CircuitBreaker()
    s = state("plan")
    assert breaker.record(s, doa_result("plan")) is None
    reason = breaker.record(s, doa_result("plan"))
    assert reason is not None and "dead-on-arrival" in reason
    assert s.cooldown_until is not None


def test_live_result_resets_instant_failure_streak():
    breaker = CircuitBreaker()
    s = state("plan")
    assert breaker.record(s, doa_result("plan")) is None
    # exit_code 0 -> a live result resets the streak even with short output
    assert breaker.record(s, result("plan", raw_output="x" * 100)) is None
    # back to a single instant failure: must not trip at the cap of 2
    assert breaker.record(s, doa_result("plan")) is None


def test_instant_failure_cap_is_configurable():
    breaker = CircuitBreaker(SafetyConfig(instant_failure_cap=3))
    s = state("plan")
    assert breaker.record(s, doa_result("plan")) is None
    assert breaker.record(s, doa_result("plan")) is None
    reason = breaker.record(s, doa_result("plan"))
    assert reason is not None and "dead-on-arrival" in reason


def test_from_budgets_reads_instant_failure_cap(tmp_path):
    budgets = tmp_path / "budgets.json"
    budgets.write_text('{"instant_failure_cap": 4}', encoding="utf-8")
    cfg = SafetyConfig.from_budgets(budgets)
    assert cfg.instant_failure_cap == 4


def test_usage_limit_detection():
    assert detect_usage_limit("Claude AI usage limit reached|1718000000")
    assert detect_usage_limit("You have hit your 5-hour limit, try again later")
    assert detect_usage_limit("You're out of extra usage · resets 9pm")
    assert detect_usage_limit(
        '{"rate_limit_event": {"info": "x", "status": "rejected"}}'
    )
    assert not detect_usage_limit("all tests passed, no limits in sight")


# --- real subscription session-limit message (S-018) ------------------------

_SESSION_LIMIT_MSG = "You've hit your session limit · resets 1:10am (America/Toronto)"


def test_session_limit_detection():
    # The real subscription message captured 2026-06-20 must be recognized.
    assert detect_usage_limit(_SESSION_LIMIT_MSG)
    # The pre-existing patterns still match their samples.
    assert detect_usage_limit("Claude AI usage limit reached|1718000000")
    assert detect_usage_limit("You have hit your 5-hour limit, try again later")
    assert detect_usage_limit("You're out of extra usage · resets 9pm")
    assert detect_usage_limit('{"rate_limit_event": {"info": "x", "status": "rejected"}}')
    # Benign prose still does not trip detection.
    assert not detect_usage_limit("all tests passed, no limits in sight")


def test_parse_reset_clause_future_today():
    tz = ZoneInfo("America/Toronto")
    # 00:30 Toronto -> the 1:10am reset is later the same day.
    now = datetime.datetime(2026, 6, 20, 0, 30, tzinfo=tz).astimezone(datetime.timezone.utc)
    parsed = _parse_usage_reset(_SESSION_LIMIT_MSG, now)
    expected = datetime.datetime(2026, 6, 20, 1, 10, tzinfo=tz).astimezone(
        datetime.timezone.utc
    )
    assert parsed == expected


def test_parse_reset_clause_rolls_to_next_day_when_passed():
    tz = ZoneInfo("America/Toronto")
    # 05:00 Toronto -> 1:10am already passed today, so roll to tomorrow.
    now = datetime.datetime(2026, 6, 20, 5, 0, tzinfo=tz).astimezone(datetime.timezone.utc)
    parsed = _parse_usage_reset(_SESSION_LIMIT_MSG, now)
    expected = datetime.datetime(2026, 6, 21, 1, 10, tzinfo=tz).astimezone(
        datetime.timezone.utc
    )
    assert parsed == expected


def test_parse_reset_clause_unknown_tz_is_none():
    # An unrecognized zone degrades to None (fallback cooldown), never raises.
    assert _parse_usage_reset("resets 1:10am (Mars/Phobos)") is None


def test_parse_reset_clause_no_parseable_time_is_none():
    assert _parse_usage_reset("your session limit will reset eventually") is None


def test_session_limit_routes_to_quotad(tmp_path):
    # A real session limit hit mid-stage (non-success, message in the output)
    # must route through the quotad path, not output-decline/dead-on-arrival.
    story = Story(id="S-001", type="feat", priority=1, title="t", description="d",
                  acceptance_criteria=["c"])

    def invoke(stage, state, story):
        return result(stage, outcome="failure", raw_output=_SESSION_LIMIT_MSG, parsed=False)

    outcome = run_ticket(
        story, invoke, state_path=tmp_path / "state.json", max_iterations=3,
        breaker=CircuitBreaker(), runs_root=tmp_path / "runs",
    )
    assert outcome.outcome == "quotad"
    assert outcome.reason == USAGE_LIMIT_HALT_REASON
    # The cooldown is stamped from the parsed reset, far beyond the generic 30m.
    s = load_state(tmp_path / "state.json")
    until = datetime.datetime.fromisoformat(s.cooldown_until)
    assert until > datetime.datetime.now(datetime.timezone.utc)


def test_usage_limit_halts_immediately():
    # A real quota cut-off: the CLI rejects the turn, so there is no clean
    # success block (parsed=False) and the usage-limit message is the output.
    breaker = CircuitBreaker()
    reason = breaker.record(
        state("plan"),
        result("plan", raw_output="Claude AI usage limit reached|1718000000", parsed=False),
    )
    assert reason is not None and "usage limit" in reason


def test_usage_limit_text_in_successful_output_does_not_halt():
    # Regression (dogfood 2026-06-19): a stage *about* usage limits (e.g. S-015)
    # writes the trigger phrases into its SUCCESSFUL result. That is not a real
    # quota halt and must not open the circuit.
    breaker = CircuitBreaker()
    s = state("plan")
    reason = breaker.record(
        s,
        result(
            "plan",
            outcome="success",
            raw_output="Plan: detect 'usage limit reached' and the 5-hour limit, "
            "parse 'usage limit reached|<epoch>', handle 'out of extra usage'.",
        ),
    )
    assert reason is None
    assert s.cooldown_until is None


def test_blocked_outcome_with_usage_limit_text_does_not_halt():
    # Regression (dogfood 2026-06-22, GH-56): a stage that correctly reports
    # `blocked` (a real verdict, not a cut-off) whose prose happens to mention
    # "session limit" must not be classified as a quota halt.
    breaker = CircuitBreaker()
    s = state("plan")
    reason = breaker.record(
        s,
        result(
            "plan",
            outcome="blocked",
            raw_output="This plan would run for hours (until the ~5h session limit), "
            "so it is blocked pending a smaller scope.",
        ),
    )
    assert reason is None
    assert s.cooldown_until is None


def test_parse_usage_reset_future_epoch():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    text = f"Claude AI usage limit reached|{int(future.timestamp())}"
    parsed = _parse_usage_reset(text)
    assert parsed is not None
    assert abs((parsed - future).total_seconds()) < 2


def test_parse_usage_reset_past_epoch_is_none():
    # The existing detection-test fixture's epoch (1718000000) is in 2024.
    assert _parse_usage_reset("Claude AI usage limit reached|1718000000") is None


def test_parse_usage_reset_no_timestamp_is_none():
    assert _parse_usage_reset("You have hit your 5-hour limit, try again later") is None


def test_usage_limit_halt_uses_parsed_reset_for_cooldown():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    breaker = CircuitBreaker()
    s = state("plan")
    reason = breaker.record(
        s,
        result(
            "plan",
            raw_output=f"Claude AI usage limit reached|{int(future.timestamp())}",
            parsed=False,
        ),
    )
    assert reason == USAGE_LIMIT_HALT_REASON
    until = datetime.datetime.fromisoformat(s.cooldown_until)
    assert abs((until - future).total_seconds()) < 2


def test_usage_limit_halt_falls_back_to_configurable_cooldown():
    breaker = CircuitBreaker()
    s = state("plan")
    reason = breaker.record(
        s,
        result("plan", raw_output="You have hit your 5-hour limit, try again later", parsed=False),
    )
    assert reason == USAGE_LIMIT_HALT_REASON
    until = datetime.datetime.fromisoformat(s.cooldown_until)
    delta = until - datetime.datetime.now(datetime.timezone.utc)
    assert delta > datetime.timedelta(minutes=200)  # far exceeds the generic 30 min


def test_non_usage_halt_still_uses_generic_cooldown():
    breaker = CircuitBreaker()
    s = state("plan")
    breaker.record(s, doa_result("plan"))
    breaker.record(s, doa_result("plan"))
    reason = breaker.record(s, doa_result("plan"))
    assert reason is not None and reason != USAGE_LIMIT_HALT_REASON
    until = datetime.datetime.fromisoformat(s.cooldown_until)
    delta = until - datetime.datetime.now(datetime.timezone.utc)
    assert delta < datetime.timedelta(minutes=35)


def test_from_budgets_reads_usage_limit_cooldown_minutes(tmp_path):
    budgets = tmp_path / "budgets.json"
    budgets.write_text('{"usage_limit_cooldown_minutes": 120}', encoding="utf-8")
    cfg = SafetyConfig.from_budgets(budgets)
    assert cfg.usage_limit_cooldown_minutes == 120


def test_from_budgets_defaults_usage_limit_cooldown_minutes(tmp_path):
    budgets = tmp_path / "budgets.json"
    budgets.write_text("{}", encoding="utf-8")
    cfg = SafetyConfig.from_budgets(budgets)
    assert cfg.usage_limit_cooldown_minutes == 300


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
    assert cfg.instant_failure_cap == 2  # default when key absent


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


def test_from_budgets_reads_permission_denial_cap(tmp_path):
    import json as _json
    from adw.safety import SafetyConfig
    path = tmp_path / "budgets.json"
    path.write_text(_json.dumps({
        "per_ticket_token_budget": 1000,
        "circuit_cooldown_minutes": 5,
        "permission_denial_cap": 10,
    }), encoding="utf-8")
    cfg = SafetyConfig.from_budgets(path)
    assert cfg.permission_denials == 10

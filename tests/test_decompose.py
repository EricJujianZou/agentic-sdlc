"""Tests for the decompose stage helpers (S-013): the criteria parser and the
run_decompose orchestration, both with a fake invoke_fn (no real agent)."""
from __future__ import annotations

from adw.invoke import StageResult
from adw.orchestrator import parse_decompose_criteria, run_decompose
from adw.status import StatusBlock
from adw.tickets import Story


def _story(criteria=None):
    return Story(id="S-001", type="feat", priority=1, title="t",
                 description="d", acceptance_criteria=criteria or [])


def _result(outcome="success", *, raw="", failure=None):
    return StageResult(
        status=StatusBlock(stage="decompose", ticket_id="S-001", outcome=outcome,
                           failure_reason=failure),
        exit_code=0, tokens_used=100, raw_output=raw,
    )


# --- parse_decompose_criteria -----------------------------------------------

def test_parse_extracts_criteria_from_status_block():
    raw = (
        'prose...\n```json\n{"stage": "decompose", "ticket_id": "S-001", '
        '"outcome": "success", "acceptance_criteria": ["one", "two"]}\n```'
    )
    assert parse_decompose_criteria(raw) == ["one", "two"]


def test_parse_cleans_blank_entries():
    raw = '{"acceptance_criteria": ["  keep  ", "", "  ", "also"]}'
    assert parse_decompose_criteria(raw) == ["keep", "also"]


def test_parse_returns_none_when_absent():
    assert parse_decompose_criteria('{"stage": "decompose", "outcome": "blocked"}') is None
    assert parse_decompose_criteria("no json here") is None
    assert parse_decompose_criteria('{"acceptance_criteria": []}') is None


# --- run_decompose ----------------------------------------------------------

def _run(result, tmp_path):
    calls = []

    def invoke(stage, state, story):
        calls.append(stage)
        return result

    criteria, problem = run_decompose(
        _story(), invoke, state_path=tmp_path / "state.json", runs_root=tmp_path / "runs",
    )
    return criteria, problem, calls


def test_run_decompose_success_returns_criteria(tmp_path):
    raw = '{"stage": "decompose", "ticket_id": "S-001", "outcome": "success", "acceptance_criteria": ["a", "b"]}'
    criteria, problem, calls = _run(_result(raw=raw), tmp_path)
    assert criteria == ["a", "b"]
    assert problem is None
    assert calls == ["decompose"]


def test_run_decompose_blocked_returns_problem(tmp_path):
    criteria, problem, _ = _run(_result("blocked", failure="too vague"), tmp_path)
    assert criteria is None
    assert "too vague" in problem


def test_run_decompose_success_without_criteria_is_a_problem(tmp_path):
    # outcome success but the agent emitted no acceptance_criteria array.
    criteria, problem, _ = _run(_result("success", raw='{"outcome": "success"}'), tmp_path)
    assert criteria is None
    assert "no acceptance_criteria" in problem


def test_run_decompose_no_status_block_is_a_problem(tmp_path):
    result = StageResult(status=None, exit_code=1, parse_error="no status block")
    criteria, problem, _ = _run(result, tmp_path)
    assert criteria is None
    assert "no status block" in problem

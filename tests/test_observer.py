"""Observer stage (self-heal lens): parsing, run_observer, and the
workflow_runner reporting that surfaces its verdict on the source issue.

No live agents or GitHub: the invoke fn is stubbed and the GitHub poster is
monkeypatched, same pattern as the rest of the suite.
"""
from pathlib import Path

import adw.workflow_runner as wr
from adw.invoke import StageResult
from adw.orchestrator import ObserverResult, parse_observer_proposal, run_observer
from adw.status import StatusBlock
from adw.tickets import Story

REPO_ROOT = Path(__file__).resolve().parent.parent

_HARNESS_RAW = (
    '{"stage":"observe","ticket_id":"GH-7","outcome":"success",'
    '"classification":"harness","repair":{"title":"system-repair: fix the test spec",'
    '"description":"the spec is ambiguous","evidence":["spec names the command","suite stays green"]},'
    '"summary":"test spec ambiguity"}'
)
_TICKET_RAW = (
    '{"stage":"observe","ticket_id":"GH-7","outcome":"success",'
    '"classification":"ticket","repair":null,"summary":"request is self-contradictory"}'
)


def _story(story_id="GH-7"):
    return Story(id=story_id, type="feat", priority=1, title="t",
                 description="d", acceptance_criteria=["a"])


def _observe_result(outcome="success", raw="", failure_reason=None, status=True):
    sb = (
        StatusBlock(stage="observe", ticket_id="GH-7", outcome=outcome,
                    summary="diag", failure_reason=failure_reason)
        if status else None
    )
    return StageResult(status=sb, exit_code=0, raw_output=raw, tokens_used=1,
                       parse_error=None if status else "no status block")


# --- parse_observer_proposal ------------------------------------------------

def test_parse_harness_proposal():
    cls, repair = parse_observer_proposal(_HARNESS_RAW)
    assert cls == "harness"
    assert repair["title"].startswith("system-repair")
    assert repair["evidence"] == ["spec names the command", "suite stays green"]


def test_parse_ticket_proposal_has_no_repair():
    cls, repair = parse_observer_proposal(_TICKET_RAW)
    assert cls == "ticket"
    assert repair is None


def test_parse_missing_or_invalid_classification():
    assert parse_observer_proposal('{"stage":"observe","outcome":"success"}') == (None, None)
    # An out-of-vocab classification is normalized away.
    assert parse_observer_proposal('{"classification":"weird"}') == (None, None)


# --- run_observer -----------------------------------------------------------

def test_run_observer_success(tmp_path):
    def invoke(stage, state, story):
        assert stage == "observe"
        assert state.last_failure == "it broke"  # failure threaded into the prompt state
        return _observe_result(raw=_HARNESS_RAW)

    res = run_observer(_story(), invoke, "it broke",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert res.problem is None
    assert res.classification == "harness"
    assert res.repair["title"].startswith("system-repair")


def test_run_observer_reports_problem_on_non_success(tmp_path):
    def invoke(stage, state, story):
        return _observe_result(outcome="blocked", failure_reason="logs unreadable")

    res = run_observer(_story(), invoke, "x",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert res.classification is None
    assert res.problem == "logs unreadable"


def test_run_observer_reports_problem_on_no_status(tmp_path):
    def invoke(stage, state, story):
        return _observe_result(status=False)

    res = run_observer(_story(), invoke, "x",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert res.problem is not None


# --- _observe_and_report ----------------------------------------------------

def test_observe_and_report_harness_posts_self_heal(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: ObserverResult(
        "harness",
        {"title": "system-repair: fix", "description": "d", "evidence": ["x", "y"]},
        "test spec ambiguity",
    ))
    posted = {}
    monkeypatch.setattr(wr, "_post_observer",
                        lambda num, body, label: posted.update(num=num, body=body, label=label))
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "it broke")
    assert posted["num"] == 7
    assert posted["label"] == wr.SELF_HEAL_LABEL
    assert "harness-level" in posted["body"]
    assert "system-repair: fix" in posted["body"]
    assert "- x" in posted["body"]  # evidence rendered as acceptance criteria


def test_observe_and_report_ticket_posts_clarify(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: ObserverResult(
        "ticket", None, "request is self-contradictory"))
    posted = {}
    monkeypatch.setattr(wr, "_post_observer",
                        lambda num, body, label: posted.update(num=num, body=body, label=label))
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "vague")
    assert posted["label"] == wr.CLARIFY_LABEL
    assert "ticket-level" in posted["body"]


def test_observe_and_report_swallows_observer_problem(monkeypatch):
    monkeypatch.setattr(wr, "run_observer",
                        lambda *a, **k: ObserverResult(None, None, "", problem="timed out"))
    called = []
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: called.append(a))
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "x")
    assert called == []  # observer couldn't analyze -> nothing posted


def test_observe_and_report_noop_for_plain_story(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: ObserverResult(
        "harness", {"title": "t", "evidence": []}, "diag"))
    called = []
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: called.append(a))
    wr._observe_and_report(_story("S-006"), lambda *a, **k: None, "x")
    assert called == []  # no source issue -> nothing to post to


# --- prompt contract --------------------------------------------------------

def test_observe_command_status_contract():
    text = (REPO_ROOT / "commands" / "OBSERVE.md").read_text(encoding="utf-8")
    assert '"stage": "observe"' in text
    assert '"classification"' in text and '"repair"' in text
    assert "no human will ever answer" in text.lower()


def test_observe_spec_exists():
    assert (REPO_ROOT / "stage_specs" / "observe.md").exists()

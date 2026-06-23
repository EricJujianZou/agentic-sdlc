"""Observer stage (self-heal lens): parsing, run_observer, and the
workflow_runner reporting that surfaces its verdict on the source issue.

No live agents or GitHub: the invoke fn is stubbed and the GitHub poster is
monkeypatched, same pattern as the rest of the suite.
"""
import datetime
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
    # A harness-classified triage escalates: sonnet triage, then the opus pass.
    calls = []

    def invoke(stage, state, story):
        calls.append(stage)
        assert state.last_failure == "it broke"  # failure threaded into the prompt state
        return _observe_result(raw=_HARNESS_RAW)

    res = run_observer(_story(), invoke, "it broke",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert calls == ["observe_triage", "observe"]
    assert res.problem is None
    assert res.classification == "harness"
    assert res.repair["title"].startswith("system-repair")


def test_run_observer_ticket_triage_does_not_escalate(tmp_path):
    # A ticket-classified triage is authoritative: one sonnet pass, no opus.
    calls = []

    def invoke(stage, state, story):
        calls.append(stage)
        return _observe_result(raw=_TICKET_RAW)

    res = run_observer(_story(), invoke, "it broke",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert calls == ["observe_triage"]
    assert res.classification == "ticket"


def test_run_observer_reports_problem_on_non_success(tmp_path):
    calls = []

    def invoke(stage, state, story):
        calls.append(stage)
        return _observe_result(outcome="blocked", failure_reason="logs unreadable")

    res = run_observer(_story(), invoke, "x",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert calls == ["observe_triage"]  # non-success triage short-circuits, no escalation
    assert res.classification is None
    assert res.problem == "logs unreadable"


def test_run_observer_reports_problem_on_no_status(tmp_path):
    def invoke(stage, state, story):
        return _observe_result(status=False)

    res = run_observer(_story(), invoke, "x",
                       state_path=tmp_path / "state.json", runs_root=tmp_path / "runs")
    assert res.problem is not None


def test_run_observer_preserves_cooldown(tmp_path):
    # After a halt that set cooldown_until, the observer's transient state write
    # must NOT wipe the breaker's pause (S-019).
    from adw.safety import check_cooldown, cooldown_remaining
    from adw.state import State, load_state, save_state

    state_path = tmp_path / "state.json"
    future = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)
    ).isoformat()
    save_state(
        State(ticket_id="GH-7", stage="plan", last_failure="circuit open: boom",
              cooldown_until=future),
        state_path,
    )

    seen = {}

    def invoke(stage, state, story):
        seen["last_failure"] = state.last_failure
        return _observe_result(raw=_HARNESS_RAW)

    run_observer(_story(), invoke, "circuit open: boom",
                 state_path=state_path, runs_root=tmp_path / "runs")

    persisted = load_state(state_path)
    assert persisted.cooldown_until == future  # cooldown carried forward, not wiped
    assert cooldown_remaining(persisted) is not None
    assert check_cooldown(state_path) is not None
    # The observer still received the failure reason for its prompt.
    assert seen["last_failure"] == "circuit open: boom"


def test_run_observer_ignores_other_ticket_cooldown(tmp_path):
    # A leftover state.json for a *different* ticket must not leak its cooldown
    # onto this observe run.
    from adw.state import State, load_state, save_state

    state_path = tmp_path / "state.json"
    future = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)
    ).isoformat()
    save_state(State(ticket_id="S-999", stage="plan", cooldown_until=future), state_path)

    run_observer(_story("GH-7"), lambda *a, **k: _observe_result(raw=_HARNESS_RAW),
                 "x", state_path=state_path, runs_root=tmp_path / "runs")

    persisted = load_state(state_path)
    assert persisted.ticket_id == "GH-7"
    assert persisted.cooldown_until is None


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


def test_is_ticket_level_failure():
    assert wr._is_ticket_level_failure("circuit open: 2 permission denials")
    assert wr._is_ticket_level_failure("PERMISSION DENIED on Bash(rm -rf:*)")
    assert wr._is_ticket_level_failure("3 tests failed in test_invoke.py")
    assert not wr._is_ticket_level_failure("vague requirements, unclear scope")
    assert not wr._is_ticket_level_failure(None)


def test_observe_and_report_skips_observer_for_ticket_level_reason(monkeypatch):
    called = []
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: called.append("observer") or None)
    posted = {}
    monkeypatch.setattr(wr, "_post_observer",
                        lambda num, body, label: posted.update(num=num, body=body, label=label))
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "circuit open: 2 permission denials")
    assert called == []  # observer never invoked
    assert posted["label"] == wr.CLARIFY_LABEL
    assert "circuit open" in posted["body"]


def test_observe_and_report_noop_for_plain_story(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: ObserverResult(
        "harness", {"title": "t", "evidence": []}, "diag"))
    called = []
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: called.append(a))
    wr._observe_and_report(_story("S-006"), lambda *a, **k: None, "x")
    assert called == []  # no source issue -> nothing to post to


# --- _file_upstream_repair (cross-repo upstream system-repair filing) -------

def _harness_result(title="fix the test spec"):
    return ObserverResult(
        "harness", {"title": title, "description": "d", "evidence": ["x"]}, "diag",
    )


def test_file_upstream_repair_cross_repo_files_issue(monkeypatch, tmp_path):
    monkeypatch.setattr(wr.paths, "target_root", lambda: tmp_path / "target")
    monkeypatch.setattr(wr.paths, "engine_root", lambda: tmp_path / "engine")
    monkeypatch.setattr(wr, "get_token", lambda: "tok")
    monkeypatch.setattr(wr, "engine_repo_slug", lambda: ("EngineOrg", "engine-repo"))
    monkeypatch.setattr(wr, "list_open_issues", lambda *a, **k: [])
    created = {}
    monkeypatch.setattr(
        wr, "create_issue",
        lambda owner, repo, token, title, body, labels=None:
            created.update(owner=owner, repo=repo, title=title, body=body, labels=labels),
    )
    wr._file_upstream_repair(_story("GH-7"), _harness_result())
    assert created["owner"] == "EngineOrg" and created["repo"] == "engine-repo"
    assert created["labels"] == [wr.SELF_HEAL_LABEL]
    assert "adw" not in created["labels"]
    assert "adw-upstream-fingerprint" in created["body"]


def test_file_upstream_repair_self_hosted_noop(monkeypatch, tmp_path):
    same = tmp_path / "repo"
    monkeypatch.setattr(wr.paths, "target_root", lambda: same)
    monkeypatch.setattr(wr.paths, "engine_root", lambda: same)
    called = []
    monkeypatch.setattr(wr, "create_issue", lambda *a, **k: called.append(a))
    wr._file_upstream_repair(_story("GH-7"), _harness_result())
    assert called == []


def test_file_upstream_repair_dedup_skips_existing(monkeypatch, tmp_path):
    monkeypatch.setattr(wr.paths, "target_root", lambda: tmp_path / "target")
    monkeypatch.setattr(wr.paths, "engine_root", lambda: tmp_path / "engine")
    monkeypatch.setattr(wr, "get_token", lambda: "tok")
    monkeypatch.setattr(wr, "engine_repo_slug", lambda: ("EngineOrg", "engine-repo"))
    fingerprint = wr._repair_fingerprint(_story("GH-7"), _harness_result())
    monkeypatch.setattr(
        wr, "list_open_issues",
        lambda *a, **k: [{"body": f"...<!-- adw-upstream-fingerprint: {fingerprint} -->"}],
    )
    called = []
    monkeypatch.setattr(wr, "create_issue", lambda *a, **k: called.append(a))
    wr._file_upstream_repair(_story("GH-7"), _harness_result())
    assert called == []


def test_file_upstream_repair_swallows_github_error(monkeypatch, tmp_path):
    from adw.github import GitHubError

    monkeypatch.setattr(wr.paths, "target_root", lambda: tmp_path / "target")
    monkeypatch.setattr(wr.paths, "engine_root", lambda: tmp_path / "engine")

    def boom():
        raise GitHubError("no token")

    monkeypatch.setattr(wr, "get_token", boom)
    wr._file_upstream_repair(_story("GH-7"), _harness_result())  # must not raise


def test_observe_and_report_files_upstream_when_cross_repo_harness(monkeypatch, tmp_path):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: _harness_result())
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: None)
    called = []
    monkeypatch.setattr(wr, "_file_upstream_repair", lambda story, result: called.append(story.id))
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "x")
    assert called == ["GH-7"]


def test_observe_and_report_files_upstream_even_without_source_issue(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: _harness_result())
    called = []
    monkeypatch.setattr(wr, "_file_upstream_repair", lambda story, result: called.append(story.id))
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: None)
    wr._observe_and_report(_story("S-006"), lambda *a, **k: None, "x")
    assert called == ["S-006"]  # plain S-NNN still has no in-repo issue, but upstream filing fires


def test_observe_and_report_no_upstream_filing_for_ticket_level(monkeypatch):
    monkeypatch.setattr(wr, "run_observer", lambda *a, **k: ObserverResult(
        "ticket", None, "request is self-contradictory"))
    called = []
    monkeypatch.setattr(wr, "_file_upstream_repair", lambda story, result: called.append(story.id))
    monkeypatch.setattr(wr, "_post_observer", lambda *a, **k: None)
    wr._observe_and_report(_story("GH-7"), lambda *a, **k: None, "x")
    assert called == []


# --- prompt contract --------------------------------------------------------

def test_observe_command_status_contract():
    text = (REPO_ROOT / "commands" / "OBSERVE.md").read_text(encoding="utf-8")
    assert '"stage": "observe"' in text
    assert '"classification"' in text and '"repair"' in text
    assert "no human will ever answer" in text.lower()


def test_observe_spec_exists():
    assert (REPO_ROOT / "stage_specs" / "observe.md").exists()


def test_observe_anchors_claims_in_git():
    # The observer must anchor every claim in git, never fabricate committed work
    # (dogfood 2026-06-20 hallucination). Guard both the spec and the command so
    # the rule cannot silently regress.
    spec = (REPO_ROOT / "stage_specs" / "observe.md").read_text(encoding="utf-8").lower()
    cmd = (REPO_ROOT / "commands" / "OBSERVE.md").read_text(encoding="utf-8").lower()
    assert "git diff" in spec and "git log" in spec
    assert "anchor" in spec or "verify" in spec
    assert "anchor every claim" in cmd

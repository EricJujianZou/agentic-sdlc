"""Tests for the shared workflow runner's test-evidence verifier (S-010).

The verifier is the orchestrator's deterministic re-run of the suite after
the dual gate. These stub subprocess.run so no real pytest is spawned, and
assert the exit code maps to pass/fail and a timeout counts as a failure.
"""
import subprocess

import adw.workflow_runner as workflow_runner
from adw.github import GitHubError
from adw.orchestrator import TicketOutcome
from adw.tickets import Story
from adw.workflow_runner import _make_verify_fn, _notify_github


class _Proc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_verify_passes_on_zero_exit_and_reports_count(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "131 passed in 4.2s"))
    verify = _make_verify_fn({"test_evidence_command": ["x"], "test_evidence_timeout_minutes": 1})
    passed, detail = verify()
    assert passed is True
    # On green, the pass count is surfaced for the outcome comment to report.
    assert detail == "131 passed"


def test_verify_passes_with_no_parseable_count(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "ok"))
    verify = _make_verify_fn({})
    passed, detail = verify()
    assert passed is True
    assert detail == ""


def test_verify_fails_on_nonzero_exit_and_keeps_detail(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _Proc(1, stdout="1 failed, 130 passed")
    )
    verify = _make_verify_fn({})  # defaults: uv run pytest -q, 10 min
    passed, detail = verify()
    assert passed is False
    assert "1 failed" in detail


def test_verify_runs_in_given_cwd(monkeypatch):
    # A parallel worker passes its worktree dir so the re-run exercises that
    # tree's changes, not the pristine main tree (#4).
    seen = {}

    def record(*a, **k):
        seen["cwd"] = k.get("cwd")
        return _Proc(0, "5 passed")

    monkeypatch.setattr(subprocess, "run", record)
    verify = _make_verify_fn({}, cwd="/tmp/.adw-worktrees/S-001")
    passed, _ = verify()
    assert passed is True
    assert seen["cwd"] == "/tmp/.adw-worktrees/S-001"


def test_verify_treats_timeout_as_failure(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    verify = _make_verify_fn({"test_evidence_timeout_minutes": 1})
    passed, detail = verify()
    assert passed is False
    assert "timed out" in detail


def _story(story_id="S-006"):
    return Story(
        id=story_id, type="feat", priority=1, title="t",
        description="d", acceptance_criteria=["a"],
    )


def test_notify_github_with_issue_id_opens_pr_and_comments(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda *a, **k: calls.setdefault("comment", (a, k)),
    )
    _notify_github(_story("GH-42"), "done", "")
    assert "pr" in calls
    assert calls["pr"][1]["head"] == "adw/GH-42"
    assert calls["pr"][1]["base"] == "main"
    assert "comment" in calls


def test_notify_github_without_issue_id_skips_comment(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda *a, **k: calls.setdefault("comment", (a, k)),
    )
    _notify_github(_story("S-006"), "done", "")
    assert "pr" in calls
    assert "comment" not in calls


def test_notify_github_swallows_github_error(monkeypatch):
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)

    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    # should not raise
    _notify_github(_story("S-006"), "blocked", "reason")


def test_notify_github_still_tries_pr_after_push_failure(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: False)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(workflow_runner, "comment_on_issue", lambda *a, **k: None)
    _notify_github(_story("S-006"), "done", "")
    assert "pr" in calls


# --- _make_progress_fn (S-014) ----------------------------------------------

def test_progress_fn_is_none_for_plain_story():
    # S-NNN has no source issue, so nothing is posted.
    assert workflow_runner._make_progress_fn(_story("S-006")) is None


def test_progress_fn_posts_to_source_issue(monkeypatch):
    posted = {}
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda owner, repo, token, num, body: posted.update(num=num, body=body),
    )
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    assert fn is not None
    fn("plan", "success")
    assert posted["num"] == 42
    assert "plan" in posted["body"] and "GH-42" in posted["body"]


def test_progress_fn_swallows_github_error(monkeypatch):
    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    fn("plan", "success")  # must not raise


def test_progress_fn_includes_summary(monkeypatch):
    posted = {}
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda owner, repo, token, num, body: posted.update(body=body),
    )
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    fn("test", "success", "209 passed, all acceptance criteria verified")
    assert "209 passed" in posted["body"]
    assert "test" in posted["body"]


# --- _finalize_story quotad (S-015) -----------------------------------------


def test_finalize_story_quotad_sets_status_label_skips_pr_and_observer(monkeypatch):
    from adw.tickets import Prd

    story = _story("S-006")
    prd = Prd(project="p", stories=[story])
    monkeypatch.setattr(workflow_runner, "load_prd", lambda path: prd)
    monkeypatch.setattr(workflow_runner, "save_prd", lambda prd, path: None)
    monkeypatch.setattr(workflow_runner, "_commit_bookkeeping", lambda message: None)

    set_label_calls = []
    monkeypatch.setattr(
        workflow_runner,
        "_set_run_label",
        lambda story, **kwargs: set_label_calls.append(kwargs),
    )

    def boom_notify(*a, **k):
        raise AssertionError("_notify_github must not be called for a quotad outcome")

    def boom_observe(*a, **k):
        raise AssertionError("_observe_and_report must not be called for a quotad outcome")

    monkeypatch.setattr(workflow_runner, "_notify_github", boom_notify)
    monkeypatch.setattr(workflow_runner, "_observe_and_report", boom_observe)

    outcome = TicketOutcome(story.id, "quotad", reason="provider usage limit reached")
    workflow_runner._finalize_story(
        story, outcome, observer_invoke=None, observer_state_path="state.json", budgets={},
    )

    assert story.status == "quotad"
    assert set_label_calls == [
        {"remove": (workflow_runner.RUN_LABEL_IN_PROGRESS,),
         "add": (workflow_runner.RUN_LABEL_QUOTAD,)}
    ]


# --- _set_run_label (S-014 follow-up) ---------------------------------------

def test_set_run_label_swaps_labels_for_issue(monkeypatch):
    added, removed = [], []
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "remove_label",
        lambda owner, repo, token, num, label: removed.append((num, label)),
    )
    monkeypatch.setattr(
        workflow_runner, "add_labels",
        lambda owner, repo, token, num, labels: added.append((num, labels)),
    )
    workflow_runner._set_run_label(
        _story("GH-42"),
        remove=(workflow_runner.RUN_LABEL_IN_PROGRESS,),
        add=(workflow_runner.RUN_LABEL_DONE,),
    )
    assert removed == [(42, "in-progress")]
    assert added == [(42, ["done"])]


def test_set_run_label_noop_for_plain_story(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not touch GitHub for a non-issue story")

    monkeypatch.setattr(workflow_runner, "get_token", fail)
    workflow_runner._set_run_label(_story("S-006"), add=(workflow_runner.RUN_LABEL_DONE,))


def test_set_run_label_swallows_github_error(monkeypatch):
    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    # Must not raise — a relabel failure can never change a ticket's outcome.
    workflow_runner._set_run_label(_story("GH-42"), add=(workflow_runner.RUN_LABEL_DONE,))

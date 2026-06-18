"""Tests for the shared workflow runner's test-evidence verifier (S-010).

The verifier is the orchestrator's deterministic re-run of the suite after
the dual gate. These stub subprocess.run so no real pytest is spawned, and
assert the exit code maps to pass/fail and a timeout counts as a failure.
"""
import subprocess

import adw.workflow_runner as workflow_runner
from adw.github import GitHubError
from adw.tickets import Story
from adw.workflow_runner import _make_verify_fn, _notify_github


class _Proc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_verify_passes_on_zero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "131 passed"))
    verify = _make_verify_fn({"test_evidence_command": ["x"], "test_evidence_timeout_minutes": 1})
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

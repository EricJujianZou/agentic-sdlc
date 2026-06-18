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

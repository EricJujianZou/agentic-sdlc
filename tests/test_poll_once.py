"""Tests for the one-shot intake->backlog runner (S-012), with injected fakes —
no live GitHub, no real workflows."""
from __future__ import annotations

from adw.workflow_runner import BacklogResult
from workflows.poll_once import poll_once


def _backlog(clean=True, ran=2, reason="reached --max-tickets (2)") -> BacklogResult:
    return BacklogResult(tickets_run=ran, stop_reason=reason, clean=clean)


def test_runs_sync_then_backlog_in_order():
    calls = []

    def sync_fn():
        calls.append("sync")
        return True, "synced"

    def backlog_fn():
        calls.append("backlog")
        return _backlog()

    res = poll_once(sync_fn=sync_fn, backlog_fn=backlog_fn)
    assert calls == ["sync", "backlog"]
    assert res.synced and res.backlog is not None
    assert res.exit_code() == 0


def test_stops_before_backlog_on_sync_failure():
    calls = []

    def sync_fn():
        calls.append("sync")
        return False, "offline"

    def backlog_fn():
        calls.append("backlog")
        return _backlog()

    res = poll_once(sync_fn=sync_fn, backlog_fn=backlog_fn)
    assert calls == ["sync"]  # backlog never runs on a failed sync
    assert res.backlog is None
    assert res.sync_message == "offline"
    assert res.exit_code() == 1


def test_max_tickets_bound_propagates_clean_exit():
    res = poll_once(
        sync_fn=lambda: (True, "synced"),
        backlog_fn=lambda: _backlog(clean=True, reason="reached --max-tickets (2)"),
    )
    assert res.exit_code() == 0
    assert "max-tickets" in res.backlog.stop_reason


def test_blocked_backlog_yields_nonzero_exit():
    res = poll_once(
        sync_fn=lambda: (True, "synced"),
        backlog_fn=lambda: _backlog(clean=False, reason="stopped at S-1: blocked"),
    )
    assert res.exit_code() == 1
    assert res.backlog.clean is False

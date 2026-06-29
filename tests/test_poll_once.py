"""Tests for the one-shot intake->backlog runner (S-012), with injected fakes —
no live GitHub, no real workflows."""
from __future__ import annotations

import datetime

from adw.workflow_runner import BacklogResult
from workflows.poll_once import (
    PollResult,
    _LOG_FIELD_CAP,
    append_log,
    default_log_path,
    format_summary_line,
    format_sync_message,
    poll_lock_path,
    poll_once,
)
from workflows.sync_issues import ROUTINE_SKIP_REASON


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


# --- self-logging (S-020) ---------------------------------------------------

_T0 = datetime.datetime(2026, 6, 20, 5, 0, 0, tzinfo=datetime.timezone.utc)


def test_log_line_for_synced_and_ran_pass():
    res = PollResult(
        synced=True,
        sync_message="synced: +1 new story(ies), 0 skipped",
        backlog=_backlog(ran=1, reason="reached --max-tickets (1)"),
    )
    line = format_summary_line(
        res, started_at=_T0, finished_at=_T0 + datetime.timedelta(seconds=12.3)
    )
    assert "2026-06-20T05:00:00Z" in line
    assert "12.3s" in line
    assert "synced: +1 new story(ies), 0 skipped" in line
    assert "ran 1 ticket(s)" in line
    assert "reached --max-tickets (1)" in line
    assert "\n" not in line  # one pass == one line


def test_log_line_for_stop_before_backlog_pass():
    res = PollResult(
        synced=False,
        sync_message="sync failed (offline or no credential?): boom",
        backlog=None,
    )
    line = format_summary_line(
        res, started_at=_T0, finished_at=_T0 + datetime.timedelta(seconds=0.4)
    )
    assert "sync failed" in line
    assert "backlog skipped" in line
    assert "0.4s" in line


def test_append_log_writes_lines_and_creates_dirs(tmp_path):
    log_path = tmp_path / "nested" / "poll.log"
    append_log(log_path, "line one")
    append_log(log_path, "line two")
    contents = log_path.read_text(encoding="utf-8")
    assert contents == "line one\nline two\n"


def test_append_log_swallows_write_failure(tmp_path):
    # A directory path can't be opened as a file -> OSError must be swallowed.
    append_log(tmp_path, "should not raise")


def test_default_log_path_is_outside_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("ADW_POLL_LOG", str(tmp_path / "custom.log"))
    assert default_log_path() == tmp_path / "custom.log"
    monkeypatch.delenv("ADW_POLL_LOG")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert default_log_path() == tmp_path / "local" / "adw" / "poll.log"


# --- single-flight lock path (race-safety) ----------------------------------


def test_poll_lock_path_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ADW_POLL_LOCK", str(tmp_path / "my.lock"))
    assert poll_lock_path() == tmp_path / "my.lock"


def test_poll_lock_path_is_per_target_and_outside_repo(monkeypatch, tmp_path):
    # Different target repos must resolve to different lock files, so a poll on
    # the engine and a poll on a cross-repo target never block each other.
    monkeypatch.delenv("ADW_POLL_LOCK", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    from adw import paths

    monkeypatch.setattr(paths, "target_root", lambda: tmp_path / "repo-a")
    a = poll_lock_path()
    monkeypatch.setattr(paths, "target_root", lambda: tmp_path / "repo-b")
    b = poll_lock_path()
    assert a != b
    assert a.parent == tmp_path / "local" / "adw" / "locks"
    assert a.suffix == ".lock"


# --- format_sync_message (GH-88) -------------------------------------------


def test_format_sync_message_non_routine_skip_named_in_log():
    """A non-routine skip (two type labels) must surface the issue ID and reason."""
    reason = "expected exactly one type label ... got ['bug', 'system-repair']"
    msg = format_sync_message([], [("GH-87", reason)])
    # The detail must appear in format_summary_line output too (AC1)
    res = PollResult(synced=True, sync_message=msg, backlog=_backlog())
    line = format_summary_line(res, started_at=_T0, finished_at=_T0)
    assert "GH-87" in line
    assert "expected exactly one type label" in line
    assert "1 skipped" in line


def test_format_sync_message_routine_skip_counted_but_not_named():
    """'already synced' skips are counted but the issue ID must not appear."""
    msg = format_sync_message([], [("GH-5", ROUTINE_SKIP_REASON)])
    assert "1 skipped" in msg
    assert "GH-5" not in msg


def test_format_sync_message_long_reason_stays_one_bounded_line():
    """A very long non-routine reason must not produce a multi-line log entry."""
    long_reason = "x" * 500
    msg = format_sync_message([], [("GH-99", long_reason)])
    res = PollResult(synced=True, sync_message=msg, backlog=_backlog())
    line = format_summary_line(res, started_at=_T0, finished_at=_T0)
    assert "\n" not in line
    # The sync field in the line is _clip'd to _LOG_FIELD_CAP; verify the full
    # line is bounded (sync field + surrounding fixed text <= some reasonable cap)
    assert len(line) <= _LOG_FIELD_CAP + 200  # generous for the fixed parts

"""Tests for the single-flight poll lock (race-safety) — no real polls."""
from __future__ import annotations

import os
import time

import pytest

from adw.locks import LockHeld, single_flight


def test_holds_then_releases(tmp_path):
    lock = tmp_path / "poll.lock"
    with single_flight(lock):
        assert lock.exists()
    assert not lock.exists()


def test_second_acquire_is_blocked_while_held(tmp_path):
    lock = tmp_path / "poll.lock"
    with single_flight(lock):
        with pytest.raises(LockHeld):
            with single_flight(lock):
                pass  # pragma: no cover — never reached


def test_lock_is_reusable_after_release(tmp_path):
    lock = tmp_path / "poll.lock"
    with single_flight(lock):
        pass
    with single_flight(lock):  # released; a fresh acquire succeeds
        assert lock.exists()


def test_released_even_on_exception(tmp_path):
    lock = tmp_path / "poll.lock"
    with pytest.raises(RuntimeError):
        with single_flight(lock):
            raise RuntimeError("boom")
    assert not lock.exists()


def test_stale_lock_is_taken_over(tmp_path):
    lock = tmp_path / "poll.lock"
    lock.write_text("999999 0\n", encoding="utf-8")  # orphaned holder
    old = time.time() - 10_000
    os.utime(lock, (old, old))  # backdate well beyond the stale window
    with single_flight(lock, stale_seconds=1):
        assert lock.exists()  # taken over, now held by us
    assert not lock.exists()


def test_fresh_lock_is_not_taken_over(tmp_path):
    lock = tmp_path / "poll.lock"
    lock.write_text("999999 0\n", encoding="utf-8")  # recent holder
    with pytest.raises(LockHeld):
        with single_flight(lock, stale_seconds=10_000):
            pass  # pragma: no cover — never reached
    assert lock.exists()  # someone else's lock is left in place


def test_creates_parent_dir(tmp_path):
    lock = tmp_path / "nested" / "deep" / "poll.lock"
    with single_flight(lock):
        assert lock.exists()

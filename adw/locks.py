"""Single-flight file lock: keep two poll passes from running against the same
target repo at once (plans/safety_plan.md).

A scheduled poll (`\\ADW\\` task) and a manually triggered sync can otherwise
interleave their prd.json read-modify-write and lose updates, race on the git
work branch, or trip over each other's `.git/index.lock`. Wrapping a whole pass
in this lock serializes them per target repo; passes against *different* repos
(engine vs a cross-repo target) use different lock files and never block each
other.

Cross-platform via an atomic `O_EXCL` create — no `fcntl`/`msvcrt`, which differ
by OS. A crashed pass would orphan the lock file, so a lock older than
`stale_seconds` is taken over rather than blocking polls forever. Staleness is
age-based on purpose: `os.kill(pid, 0)` is not a safe liveness probe on Windows
(it can terminate the process), so we do not probe the PID.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Two hours: comfortably longer than any real pass (a --max-tickets run is
# breaker-bounded), short enough that a crash-orphaned lock self-heals within a
# couple of hourly cycles. Overridable by the caller.
DEFAULT_STALE_SECONDS = 2 * 60 * 60


class LockHeld(RuntimeError):
    """A live holder owns the lock; the caller should skip this pass, not wait."""


def _try_create(path: Path) -> int | None:
    """Atomically create the lock file, or None if it already exists."""
    try:
        return os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None


def _lock_age_seconds(path: Path) -> float | None:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None  # vanished between the failed create and the stat


@contextmanager
def single_flight(
    lock_path: str | Path, *, stale_seconds: float = DEFAULT_STALE_SECONDS
) -> Iterator[None]:
    """Hold an exclusive lock for the duration of the block, or raise `LockHeld`.

    On contention, a lock file older than `stale_seconds` is treated as orphaned
    by a crashed pass: it is removed and creation is retried once (the `O_EXCL`
    create means only one racer wins that retry; the rest still get `LockHeld`).
    The lock is always released in `finally`.
    """
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = _try_create(path)
    if fd is None:
        age = _lock_age_seconds(path)
        if age is not None and age > stale_seconds:
            try:
                path.unlink()
            except OSError:
                pass
            fd = _try_create(path)
        if fd is None:
            raise LockHeld(f"another poll holds {path} (age={age}s)")
    try:
        try:
            os.write(fd, f"{os.getpid()} {int(time.time())}\n".encode())
        finally:
            os.close(fd)
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass

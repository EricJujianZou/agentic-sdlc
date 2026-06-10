"""progress.txt: bounded tactical learnings (plans/tickets_plan.md §4).

A hot cache, not a log. Agents append and prune; the harness (Stop hook,
workflow) enforces the hard cap mechanically via assert_under_cap.
"""
from __future__ import annotations

from pathlib import Path

LINE_CAP = 100


class ProgressCapExceeded(RuntimeError):
    """progress.txt is over its line cap; the run must prune before it can complete."""


def line_count(path: str | Path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8").splitlines())


def is_over_cap(path: str | Path, cap: int = LINE_CAP) -> bool:
    return line_count(path) > cap


def assert_under_cap(path: str | Path, cap: int = LINE_CAP) -> None:
    count = line_count(path)
    if count > cap:
        raise ProgressCapExceeded(
            f"{path} has {count} lines (cap {cap}). Prune: durable patterns -> skills/, "
            "harness bugs -> system-repair ticket, stale notes -> delete."
        )


def append_entry(path: str | Path, entry: str) -> None:
    """Append one learning entry. Caller is responsible for pruning to the cap."""
    p = Path(path)
    existing = p.read_text(encoding="utf-8") if p.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    p.write_text(existing + entry.rstrip("\n") + "\n", encoding="utf-8")

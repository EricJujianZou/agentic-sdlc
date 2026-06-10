"""Per-run logs: hand-offs within one run, deleted after merge/blocked-review.

plans/harness_plan.md §5 — no append-forever logs. observability/history.md
(human-only) and git log are the durable records.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

DEFAULT_RUNS_ROOT = Path("observability") / "runs"


def run_dir(ticket_id: str, runs_root: str | Path = DEFAULT_RUNS_ROOT) -> Path:
    path = Path(runs_root) / ticket_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_stage_log(
    ticket_id: str,
    *,
    stage: str,
    iteration: int,
    payload: dict,
    runs_root: str | Path = DEFAULT_RUNS_ROOT,
) -> Path:
    path = run_dir(ticket_id, runs_root) / f"iter{iteration:02d}_{stage}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def cleanup_run(ticket_id: str, runs_root: str | Path = DEFAULT_RUNS_ROOT) -> None:
    """Delete a ticket's run logs once it merges or is blocked-and-reviewed."""
    path = Path(runs_root) / ticket_id
    if path.exists():
        shutil.rmtree(path)


def append_history_line(
    ticket_id: str,
    summary: str,
    history_path: str | Path = Path("observability") / "history.md",
) -> None:
    """One human-only line per merged ticket; agents never read this."""
    path = Path(history_path)
    line = f"- {_dt.date.today().isoformat()} {ticket_id}: {summary}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)

"""Per-run logs: hand-offs within one run, deleted after merge/blocked-review.

plans/harness_plan.md §5 — no append-forever logs. observability/history.md
(human-only) and git log are the durable records.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

from adw import paths

# Run logs and history live in the *target* repo (adw/paths.py). The defaults
# are None so they resolve at call time — a process can change ADW_REPO and the
# next call lands in the right repo. Callers (tests) may still pass an explicit
# runs_root to redirect to a temp dir.


def run_dir(ticket_id: str, runs_root: str | Path | None = None) -> Path:
    path = Path(runs_root if runs_root is not None else paths.runs_root()) / ticket_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_stage_log(
    ticket_id: str,
    *,
    stage: str,
    iteration: int,
    payload: dict,
    runs_root: str | Path | None = None,
) -> Path:
    path = run_dir(ticket_id, runs_root) / f"iter{iteration:02d}_{stage}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def cleanup_run(ticket_id: str, runs_root: str | Path | None = None) -> None:
    """Delete a ticket's run logs once it merges or is blocked-and-reviewed."""
    path = Path(runs_root if runs_root is not None else paths.runs_root()) / ticket_id
    if path.exists():
        shutil.rmtree(path)


def append_history_line(
    ticket_id: str,
    summary: str,
    history_path: str | Path | None = None,
) -> None:
    """One human-only line per merged ticket; agents never read this."""
    path = Path(history_path if history_path is not None else paths.history_path())
    line = f"- {_dt.date.today().isoformat()} {ticket_id}: {summary}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)

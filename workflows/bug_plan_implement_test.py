"""Bug workflow: pick -> plan -> implement -> test (no review stage).

Usage: uv run python workflows/bug_plan_implement_test.py [--ticket S-NNN] [--max-iterations N]

A bug fix needs a plan and a fix, but the gate is regression evidence: the
test stage's success (acceptance criteria verified) is what closes the
ticket, so there is no separate review stage. Thin entry point — all
deterministic control flow lives in adw.workflow_runner.run_workflow.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw.workflow_runner import run_workflow

STAGE_ORDER = ("plan", "implement", "test")

if __name__ == "__main__":
    raise SystemExit(
        run_workflow(STAGE_ORDER, ticket_types=("bug",), description=__doc__)
    )

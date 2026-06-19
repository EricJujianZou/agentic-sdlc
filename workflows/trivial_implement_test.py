"""Trivial workflow: pick -> implement -> test, for chore-sized changes.

Usage: uv run python workflows/trivial_implement_test.py [--ticket S-NNN] [--max-iterations N]

A chore is small enough to skip planning: implement straight from the
ticket, then let the test stage's success be the gate. Thin entry point —
all deterministic control flow lives in adw.workflow_runner.run_workflow.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw.workflow_runner import run_workflow

STAGE_ORDER = ("implement", "test")

if __name__ == "__main__":
    raise SystemExit(
        run_workflow(STAGE_ORDER, ticket_types=("chore",), description=__doc__)
    )

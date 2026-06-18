"""Full-cycle workflow for feat tickets: pick -> plan -> implement -> test -> review.

Usage: uv run python workflows/feat_full_cycle.py [--ticket S-001] [--max-iterations N]

Thin entry point: it declares the stage order and the ticket types it serves,
then hands off to adw.workflow_runner.run_workflow, where all deterministic
control flow lives. Stage prompts are composed from commands/<STAGE>.md;
this script never hardcodes prompt content.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw.orchestrator import STAGE_ORDER
from adw.workflow_runner import run_workflow

# feat and system-repair tickets both want the full plan->implement->test->
# review cycle: review's exit_signal is the completion gate for each.
FEAT_TICKET_TYPES = ("feat", "system-repair")

if __name__ == "__main__":
    raise SystemExit(
        run_workflow(STAGE_ORDER, ticket_types=FEAT_TICKET_TYPES, description=__doc__)
    )

"""state.json: the minimal hand-off between stages of one ticket.

Schema owned by plans/tickets_plan.md §3. Nothing goes in here that git
(diff, log, branch) can already answer. Reset per ticket.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STAGES = ("plan", "implement", "test", "review")


@dataclass
class State:
    ticket_id: str
    stage: str = "plan"
    iteration: int = 1
    branch: str = ""
    last_failure: str | None = None
    budget_used_tokens: int = 0

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}, got {self.stage!r}")
        if not self.branch:
            self.branch = f"adw/{self.ticket_id}"


def new_state(ticket_id: str) -> State:
    """Fresh state for a just-picked ticket (resets everything)."""
    return State(ticket_id=ticket_id)


def load_state(path: str | Path) -> State:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return State(
        ticket_id=raw["ticket_id"],
        stage=raw["stage"],
        iteration=raw["iteration"],
        branch=raw["branch"],
        last_failure=raw.get("last_failure"),
        budget_used_tokens=raw.get("budget_used_tokens", 0),
    )


def save_state(state: State, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")

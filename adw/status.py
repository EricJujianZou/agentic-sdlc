"""Structured status block: the stage I/O contract (plans/harness_plan.md §2).

Every stage must end its output with a JSON status block. The workflow
parses it as the ONLY completion signal — agent prose counts for nothing
(plans/safety_plan.md §1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from adw.state import STAGES

OUTCOMES = ("success", "failure", "blocked")
REQUIRED_KEYS = ("stage", "ticket_id", "outcome")


class StatusBlockError(ValueError):
    """No parseable status block found, or the block violates the contract."""


@dataclass
class StatusBlock:
    stage: str
    ticket_id: str
    outcome: str
    exit_signal: bool = False
    summary: str = ""
    failure_reason: str | None = None
    files_changed: int = 0
    suggested_tools: list[str] = field(default_factory=list)
    system_repair_suggested: bool = False


def _candidate_objects(text: str):
    """Yield every JSON object decodable from the text, last first."""
    decoder = json.JSONDecoder()
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in reversed(starts):
        try:
            obj, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def parse_status_block(text: str) -> StatusBlock:
    """Extract the last status block from a stage's output text."""
    for obj in _candidate_objects(text):
        if not all(key in obj for key in REQUIRED_KEYS):
            continue
        if obj["outcome"] not in OUTCOMES:
            raise StatusBlockError(
                f"outcome must be one of {OUTCOMES}, got {obj['outcome']!r}"
            )
        if obj["stage"] not in STAGES:
            raise StatusBlockError(f"stage must be one of {STAGES}, got {obj['stage']!r}")
        return StatusBlock(
            stage=obj["stage"],
            ticket_id=obj["ticket_id"],
            outcome=obj["outcome"],
            exit_signal=bool(obj.get("exit_signal", False)),
            summary=obj.get("summary", ""),
            failure_reason=obj.get("failure_reason"),
            files_changed=int(obj.get("files_changed", 0)),
            suggested_tools=list(obj.get("suggested_tools", [])),
            system_repair_suggested=bool(obj.get("system_repair_suggested", False)),
        )
    raise StatusBlockError("no status block found in stage output")

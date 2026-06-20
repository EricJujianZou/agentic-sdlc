"""Circuit breaker, budgets, and cooldown (plans/safety_plan.md §2–§3).

Implements the orchestrator's `Breaker` protocol. Thresholds adapted from
frankbria/ralph-claude-code `lib/circuit_breaker.sh`; usage-limit detection
adapted from its `ralph_loop.sh` layered text matching. Opening the circuit
writes a cooldown timestamp into state.json so no auto-retry can start
before it elapses — a blocked run requires human attention.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from adw.invoke import StageResult
from adw.state import State, load_state

# Provider 5-hour usage limit / extra-usage quota, per ralph_loop.sh layers
# 2-4: the CLI's rate_limit_event JSON, then text fallbacks.
_USAGE_LIMIT_PATTERNS = (
    re.compile(r'"rate_limit_event"[\s\S]{0,300}?"status"\s*:\s*"rejected"'),
    re.compile(r"5.?hour.{0,40}?limit", re.IGNORECASE),
    re.compile(r"usage.{0,20}?limit.{0,20}?reached", re.IGNORECASE),
    re.compile(r"limit.{0,40}?reached.{0,40}?try.{0,20}?back", re.IGNORECASE),
    re.compile(r"out of extra usage", re.IGNORECASE),
)


def detect_usage_limit(text: str) -> bool:
    """True if the output signals the provider's usage limit was hit."""
    return any(p.search(text) for p in _USAGE_LIMIT_PATTERNS)


# The one halt-reason string a real quota cut-off returns from `_evaluate`.
# `record`'s cooldown branch and `orchestrator.run_ticket`'s outcome branch
# both compare against this constant (not against `detect_usage_limit`
# directly) so they classify exactly what the breaker decided, never drifting
# from each other or re-detecting text the breaker already gated on success.
USAGE_LIMIT_HALT_REASON = "provider usage limit reached; pausing instead of looping"

# Layer 2-4 reset-time hints, per ralph_loop.sh: a trailing Unix-epoch-seconds
# value (the real Claude CLI "usage limit reached|<epoch>" form) or an
# ISO-8601 timestamp anywhere in the message.
_EPOCH_SUFFIX_RE = re.compile(r"\|(\d{9,})\b")
_ISO_TIMESTAMP_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)


def _parse_usage_reset(text: str, now: _dt.datetime | None = None) -> _dt.datetime | None:
    """Absolute UTC reset instant parsed out of a usage-limit message, or None
    if no parseable reset is present, or if the parsed instant is not in the
    future (a stale/test epoch must not stamp an already-expired cooldown)."""
    now = now or _utcnow()
    match = _EPOCH_SUFFIX_RE.search(text)
    if match:
        candidate = _dt.datetime.fromtimestamp(int(match.group(1)), tz=_dt.timezone.utc)
        if candidate > now:
            return candidate
    match = _ISO_TIMESTAMP_RE.search(text)
    if match:
        try:
            candidate = _dt.datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
        except ValueError:
            return None
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=_dt.timezone.utc)
        if candidate > now:
            return candidate
    return None


@dataclass
class SafetyConfig:
    """Thresholds per plans/safety_plan.md §2 table and §3 budgets."""

    no_change_loops: int = 3
    same_error_loops: int = 5
    output_decline_pct: int = 70
    # Decline is only meaningful against a substantial baseline; tiny prior
    # outputs would make any short (possibly legitimate) reply trip it.
    output_decline_floor_chars: int = 1500
    permission_denials: int = 2
    instant_failure_cap: int = 2
    per_ticket_token_budget: int | None = None
    cooldown_minutes: int = 30
    # A usage-limit halt's reset is typically ~5h out, far longer than the
    # generic circuit_cooldown_minutes; used only when no reset time can be
    # parsed out of the halt text (see _parse_usage_reset).
    usage_limit_cooldown_minutes: int = 300

    @classmethod
    def from_budgets(cls, path: str | Path) -> "SafetyConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            per_ticket_token_budget=raw.get("per_ticket_token_budget"),
            cooldown_minutes=raw.get("circuit_cooldown_minutes", cls.cooldown_minutes),
            usage_limit_cooldown_minutes=raw.get(
                "usage_limit_cooldown_minutes", cls.usage_limit_cooldown_minutes
            ),
            permission_denials=raw.get("permission_denial_cap", cls.permission_denials),
            instant_failure_cap=raw.get("instant_failure_cap", cls.instant_failure_cap),
        )


@dataclass
class CircuitBreaker:
    """Stateful per-run breaker; create a fresh one per ticket run.

    `record` returns a halt reason to open the circuit, or None. Opening
    also stamps `state.cooldown_until` (the orchestrator persists state
    right after), so `check_cooldown` blocks auto-retries until it passes.
    """

    config: SafetyConfig = field(default_factory=SafetyConfig)
    _no_change_streak: int = 0
    _error_streak: int = 0
    _last_error: str | None = None
    _denials_total: int = 0
    _instant_failure_streak: int = 0
    _prev_output_len: dict[str, int] = field(default_factory=dict)

    def record(self, state: State, result: StageResult) -> str | None:
        reason = self._evaluate(state, result)
        if reason is not None:
            until = _utcnow() + _dt.timedelta(minutes=self.config.cooldown_minutes)
            state.cooldown_until = until.isoformat()
        return reason

    def _evaluate(self, state: State, result: StageResult) -> str | None:
        cfg = self.config

        # A genuine provider usage limit cuts the stage's turn off, so it can
        # never also return a clean *successful* status block. Gate detection on
        # a non-successful result: otherwise a stage whose very subject is usage
        # limits (e.g. S-015) trips the matcher on its own prose and self-halts
        # (dogfood 2026-06-19 false positive — the plan succeeded with 18k tokens
        # yet "usage limit reached" in its plan text opened the circuit). The CLI
        # surfaces a real limit in the result text and/or stderr; scan both, but
        # only when the stage did not succeed.
        stage_succeeded = result.status is not None and result.status.outcome == "success"
        if not stage_succeeded and detect_usage_limit(
            f"{result.raw_output}\n{result.stderr}"
        ):
            return "provider usage limit reached; pausing instead of looping"

        # Dead-on-arrival: the CLI exited non-zero having produced nothing
        # (0 tokens, empty output). The same-error rule (5 loops) can never
        # catch this before max_iterations under default budgets, so trip
        # fast on a short consecutive streak (test_run1.md follow-up 1).
        if (
            result.exit_code != 0
            and result.tokens_used == 0
            and not result.raw_output.strip()
        ):
            self._instant_failure_streak += 1
            if self._instant_failure_streak >= cfg.instant_failure_cap:
                return (
                    f"circuit open: {self._instant_failure_streak} consecutive "
                    "dead-on-arrival stage results (exit!=0, 0 tokens, no output)"
                )
        else:
            self._instant_failure_streak = 0

        self._denials_total += result.permission_denials
        if self._denials_total >= cfg.permission_denials:
            return f"circuit open: {self._denials_total} permission denials"

        if cfg.per_ticket_token_budget is not None and (
            state.budget_used_tokens > cfg.per_ticket_token_budget
        ):
            return (
                f"circuit open: token budget exceeded "
                f"({state.budget_used_tokens} > {cfg.per_ticket_token_budget})"
            )

        # No-file-change stagnation: only implement is expected to change
        # files, so only implement feeds the streak (plan/test/review with
        # zero changes are healthy).
        if state.stage == "implement":
            files = result.status.files_changed if result.status else 0
            if files == 0:
                self._no_change_streak += 1
            else:
                self._no_change_streak = 0
            if self._no_change_streak >= cfg.no_change_loops:
                return (
                    f"circuit open: {self._no_change_streak} implement loops "
                    "with no file changes"
                )

        error = self._error_signature(result)
        if error is None:
            self._error_streak, self._last_error = 0, None
        elif error == self._last_error:
            self._error_streak += 1
        else:
            self._error_streak, self._last_error = 1, error
        if self._error_streak >= cfg.same_error_loops:
            return f"circuit open: same error {self._error_streak} times ({error})"

        prev = self._prev_output_len.get(state.stage)
        cur = len(result.raw_output)
        self._prev_output_len[state.stage] = cur
        if (
            prev is not None
            and prev >= cfg.output_decline_floor_chars
            and cur < prev * (100 - cfg.output_decline_pct) / 100
        ):
            return (
                f"circuit open: {state.stage} output declined "
                f">{cfg.output_decline_pct}% ({prev} -> {cur} chars)"
            )

        return None

    @staticmethod
    def _error_signature(result: StageResult) -> str | None:
        if result.status is None:
            return (result.parse_error or "no status block").strip().lower()
        if result.status.outcome == "failure":
            return (result.status.failure_reason or "unspecified failure").strip().lower()
        return None


def cooldown_remaining(state: State, now: _dt.datetime | None = None) -> _dt.timedelta | None:
    """Time left on an open circuit's cooldown, or None if none is active."""
    if not state.cooldown_until:
        return None
    until = _dt.datetime.fromisoformat(state.cooldown_until)
    now = now or _utcnow()
    if until.tzinfo is None:
        until = until.replace(tzinfo=_dt.timezone.utc)
    remaining = until - now
    return remaining if remaining > _dt.timedelta(0) else None


def check_cooldown(state_path: str | Path) -> str | None:
    """Refusal message if the previous run's cooldown is still active."""
    path = Path(state_path)
    if not path.exists():
        return None
    try:
        state = load_state(path)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None  # unreadable state never blocks a fresh attended run
    remaining = cooldown_remaining(state)
    if remaining is None:
        return None
    minutes = int(remaining.total_seconds() // 60) + 1
    return (
        f"circuit cooldown active for ~{minutes} more minute(s) "
        f"(until {state.cooldown_until}); last failure: {state.last_failure}"
    )


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)

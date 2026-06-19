"""Headless stage invocation: `claude -p` with scoped tools (plans/harness_plan.md §1).

Prompts are data — file paths in, structured JSON out. This module never
composes prompt content; it only runs what the workflow points it at.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from adw import isolation
from adw.status import StatusBlock, StatusBlockError, parse_status_block

# Per-stage tool scoping: plan is read-only; implement gets edit+bash;
# test gets bash+Playwright; review is read-only+Playwright.
# Read-only stages still get scoped git inspection commands: PRIME.md
# requires `git status`/`git log` and REVIEW.md requires `git diff` — an
# unscoped denial there trips the breaker's permission-denial counter.
_GIT_READONLY = ["Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)"]
STAGE_TOOLS: dict[str, list[str]] = {
    # decompose only reads the repo to expand a terse ticket into acceptance
    # criteria; it never edits, and the orchestrator (not the agent) persists
    # the result to prd.json.
    "decompose": ["Read", "Glob", "Grep", *_GIT_READONLY],
    "plan": ["Read", "Glob", "Grep", *_GIT_READONLY],
    "implement": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "test": ["Read", "Glob", "Grep", "Bash", "mcp__playwright"],
    "review": ["Read", "Glob", "Grep", "mcp__playwright", *_GIT_READONLY],
    # observe runs read-only on a non-done ticket to diagnose root cause across
    # the whole repo (self-heal lens); it proposes, never edits or commits.
    "observe": ["Read", "Glob", "Grep", *_GIT_READONLY],
    "document": ["Read", "Glob", "Grep", "Write", *_GIT_READONLY, "Bash(git add:*)", "Bash(git commit:*)"],
}

DEFAULT_TIMEOUT_SECONDS = 15 * 60


@dataclass
class StageResult:
    status: StatusBlock | None
    exit_code: int
    timed_out: bool = False
    tokens_used: int = 0
    cost_usd: float = 0.0
    raw_output: str = ""
    stderr: str = ""
    parse_error: str | None = None
    permission_denials: int = 0
    session_id: str | None = None
    suggested_tools: list[str] = field(default_factory=list)


def build_command(
    *,
    stage: str,
    model: str,
    claude_bin: str | None = None,
) -> list[str]:
    """Argv for one headless stage. The prompt is NOT in the argv: it goes
    to the CLI via stdin, because the Windows npm shim (claude.cmd) routes
    argv through cmd.exe, which mangles multi-line arguments.

    `claude_bin` overrides how the CLI is located: the host path defaults to
    the PATHEXT-resolved shim, but the containerized path passes a bare
    "claude" so it resolves against the image's PATH, not the host's."""
    if stage not in STAGE_TOOLS:
        raise ValueError(f"stage must be one of {tuple(STAGE_TOOLS)}, got {stage!r}")
    # On Windows the CLI is an npm shim (claude.cmd), which CreateProcess
    # cannot resolve from a bare name with shell=False; which() returns the
    # full PATHEXT-resolved path on every platform.
    return [
        claude_bin or shutil.which("claude") or "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--allowedTools",
        ",".join(STAGE_TOOLS[stage]),
    ]


def _parse_envelope(stdout: str) -> tuple[str, int, float, str | None, int]:
    """Return (result_text, total_tokens, cost_usd, session_id, permission_denials)
    from the CLI JSON envelope."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        # Envelope itself unparseable — fall back to raw text for status extraction.
        return stdout, 0, 0.0, None, 0
    usage = envelope.get("usage", {}) or {}
    tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    cost = float(envelope.get("total_cost_usd", 0.0))
    denials = envelope.get("permission_denials") or []
    denial_count = len(denials) if isinstance(denials, list) else int(denials)
    return (
        envelope.get("result", "") or "",
        tokens,
        cost,
        envelope.get("session_id"),
        denial_count,
    )


def invoke_stage(
    prompt_path: str | Path,
    *,
    stage: str,
    model: str,
    cwd: str | Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> StageResult:
    """Run one stage headlessly and parse its status block.

    A timeout is reported, not raised: the workflow decides whether it was
    productive (files changed) via git, per the circuit-breaker rules.
    """
    prompt_path = Path(prompt_path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"stage prompt not found: {prompt_path}")
    # Isolation off (default) is the documented fallback: build and run the
    # stage on the bare host exactly as before. Isolation on wraps the same
    # CLI argv in `docker run`, mounting only the repo (cwd) and passing only
    # scoped env across the boundary (plans/safety_plan.md §5, adw/isolation.py).
    if isolation.isolation_enabled():
        cmd = isolation.build_run_command(
            build_command(stage=stage, model=model, claude_bin="claude"),
            repo_dir=cwd,
            stage=stage,
        )
    else:
        cmd = build_command(stage=stage, model=model)
    # ADW_TICKET_RUN switches the hooks (hooks/*.py) into enforcement mode:
    # harness-file edit denial, Stop checklist, auto-commit. ADW_STAGE lets
    # stage-aware hooks skip checks a stage cannot satisfy (a read-only
    # planner cannot commit, so the clean-tree gate must not bind it).
    # Under isolation these are also injected into the container via -e so the
    # in-container hooks see them; setting them here too is harmless and keeps
    # the host path unchanged.
    env = {**os.environ, "ADW_TICKET_RUN": "1", "ADW_STAGE": stage}
    try:
        proc = subprocess.run(
            cmd,
            input=prompt_path.read_text(encoding="utf-8"),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            shell=False,
            env=env,
        )
        stdout, stderr_text, exit_code, timed_out = (
            proc.stdout or "", proc.stderr or "", proc.returncode, False
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr_text = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        exit_code, timed_out = 124, True

    result_text, tokens, cost, session_id, denials = _parse_envelope(stdout)
    status: StatusBlock | None = None
    parse_error: str | None = None
    try:
        status = parse_status_block(result_text)
    except StatusBlockError as exc:
        parse_error = str(exc)
    return StageResult(
        status=status,
        exit_code=exit_code,
        timed_out=timed_out,
        tokens_used=tokens,
        cost_usd=cost,
        raw_output=result_text,
        stderr=stderr_text,
        parse_error=parse_error,
        permission_denials=denials,
        session_id=session_id,
        suggested_tools=status.suggested_tools if status else [],
    )

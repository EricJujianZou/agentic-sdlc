---
name: harness-plan
description: Orchestrator subsystem — the deterministic .py workflows: headless agent invocation, structured status blocks, data flow, model-per-phase config, parallelization, and observability/log retention.
read_when: Building or modifying workflows/*.py; defining the stage I/O contract; configuring models or budgets; setting up run logging.
sdlc_stage: build-time; the workflow itself runs at every stage
---

# Harness Plan

The workflow is the only component with authority: it spawns stages, parses their output, enforces safety bounds (see `plans/safety_plan.md`), and decides transitions.

## 1. Headless invocation

- Stages are invoked via Claude Code headless mode: `claude -p "<stage prompt>" --output-format json` (plus `--allowedTools` scoped per stage).
- Prompts are data: passed as flags or file paths, never hardcoded in Python strings. Explicit file paths in, structured JSON out — deterministic data flow end to end.
- Per-stage tool scoping: plan gets read-only tools; implement gets edit+bash; test gets bash+Playwright; review gets read-only+Playwright.

## 2. Structured status block (stage I/O contract)

Every stage must end its output with:

```json
{
  "stage": "implement",
  "ticket_id": "S-001",
  "outcome": "success | failure | blocked",
  "exit_signal": false,
  "summary": "one or two lines",
  "failure_reason": "null or one line",
  "files_changed": 7,
  "suggested_tools": ["optional: tool to adopt, with reference repo from the relevant plan"],
  "system_repair_suggested": false
}
```

The workflow parses this (it is the *only* completion signal — see safety plan), updates `state.json`, and routes: success → next stage; failure → bounded loop back to plan; blocked → halt for human.

## 3. Model-per-phase config

`configs/models.json` — deterministic, no in-prompt model choices:

| Phase | Default tier | Rationale |
|---|---|---|
| decompose / plan / review | Opus-tier | Judgment-heavy; errors here are expensive downstream |
| implement | Sonnet-tier | Volume work; bounded by tests and review |
| trivial tickets, classification steps | Haiku-tier | Cheap, fast |

Budgets per phase live in `configs/budgets.json` (enforced per safety plan).

## 4. Parallelization

- Independent tickets may run in parallel via **git worktrees**, one worktree + one workflow process per ticket.
- Never two agents in one worktree. Merge-gate serializes integration to main.

## 5. Observability & log retention

- Per-run logs under `observability/runs/<ticket-id>/` are **hand-offs within one run**: the workflow deletes them after the ticket merges or is blocked-and-reviewed. No append-forever logs.
- `state.json` carries per-stage token usage for budget enforcement.
- `observability/history.md` (human-only, written at merge) is the durable record; git log is the detailed one.

## Reference repos — adopt before building

| Tool need | Repo | What to take |
|---|---|---|
| Loop skeleton: fresh instance per iteration, story selection, quality-check gate | `snarktank/ralph` | `ralph.sh` structure (port to Python), `--tool claude` invocation pattern, max-iterations arg |
| Production loop engineering: status parsing, JSON-mode handling, timeout guards | `frankbria/ralph-claude-code` | `ralph_loop.sh` three-layer output verification, RALPH_STATUS block design |
| Headless mode / programmatic invocation | Official Claude Code docs (headless/SDK) | `claude -p`, `--output-format json`, `--allowedTools` |
| Orchestrator survey (avoid rebuilding) | `hesreallyhim/awesome-claude-code` | Agent-orchestrator section — check for existing Python harnesses before extending ours |

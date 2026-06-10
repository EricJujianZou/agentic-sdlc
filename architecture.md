---
name: architecture
description: System architecture for the agentic SDLC harness — layers, data flow, memory model, context isolation, and directory layout. Pure architecture; implementation detail lives in plans/.
read_when: Onboarding to the system, making structural decisions, or resolving questions about how components relate. Not needed for executing a single stage of a single ticket.
sdlc_stage: all
---

# Agentic SDLC — Architecture

## Purpose

A harness that takes a human-written ticket and autonomously carries it through plan → implement → test → review → merge gate, using fresh Claude Code instances per stage, deterministic Python orchestration, and git as the durable memory layer. Scope: personal projects, single developer, unattended runs must be safe by construction.

## Layer model

```
Trigger (prd.json ticket)
   ↓
Workflow (deterministic .py orchestrator — owns all control flow)
   ↓
Stage (fresh Claude Code instance per stage, headless mode)
   ↓ reads
Commands / Stage Specs / Skills (prompt assets — own all intelligence)
```

- **Trigger** — a story in `prd.json` with `passes: false`. The orchestrator picks the highest-priority open story. No dashboards or external ticket tools in v1. See `plans/tickets_plan.md`.
- **Workflows** ("adw" — agentic development workflows) — Python scripts (`workflows/`), one per ticket type (e.g. `feat_full_cycle.py`, `bug_plan_implement_test.py`, `trivial_implement_test.py`). They sequence stages, enforce loop bounds, parse stage output, and decide transitions. Workflows are code, never markdown. All determinism lives here. See `plans/harness_plan.md`.
- **Stages** — each SDLC stage (plan, implement, test, review) runs as a **fresh agent instance** invoked headlessly by the workflow. A stage receives: the ticket, `state.json`, and pointers to the prompt assets it needs. It ends by emitting a structured status block the orchestrator parses. No agent survives across stages.
- **Commands** (`commands/`) — lightweight reusable prompts (e.g. `/PRIME` for codebase orientation). See `plans/prompts_plan.md`.
- **Stage specs** (`stage_specs/`) — the contract for each stage per ticket type: exact plan format, test requirements, review criteria. (Formerly called "metaprompts" — renamed because they are specifications/contracts, not prompt-generators.)
- **Skills** (`skills/`) — cached solutions to *classes* of problems (build an API, add a frontend page, create an MCP server), implemented in the Claude Code Skills format: front-matter description always in context, full body read on demand. When a ticket matches a solved class, stages follow the skill instead of re-deriving the approach. Specific ticket plans are never preserved; skills are.

## Memory model

Git is the single durable source of truth. Three small files supplement it:

| File | Holds | Bound |
|---|---|---|
| `prd.json` | Stories with acceptance criteria and `passes` flags | One file per project |
| `state.json` | Current ticket, stage, iteration count, last failure reason | Minimal schema — nothing git can already answer |
| `progress.txt` | Tactical learnings appended per run | Hard size cap; pruned every run; durable patterns graduate into skills, structural fixes into system tickets |

Anything not in git or these three files does not exist between stages. Schemas in `plans/tickets_plan.md`.

## Context isolation

The unit of isolation is **one stage of one small ticket**. Two rules enforce it:

1. Fresh agent per stage — the workflow terminates the instance at each stage boundary; the next stage starts cold from git + `state.json`. No single agent for everything; no parallel subagent swarms (one exception: read-only explorer subagents for codebase search).
2. Tickets must be decomposed until a single stage fits comfortably in one context window. Decomposition is a gated step with its own rules (see `plans/tickets_plan.md`) — spec quality is the highest-leverage variable in the whole system.

## The SDLC loop

```
pick ticket → plan → implement → test ─┬→ review ─┬→ merge gate (human or deterministic)
                ↑                      │           │
                └──── bounded loop ←───┴───────────┘
```

- **test** validates mechanics: build, smoke, unit, regression.
- **review** validates intent (does the result reflect the ticket) plus code quality/security and, for frontend tickets, visual verification.
- Failures route back to plan **through the orchestrator**, which enforces max-iteration caps, no-progress detection, and budget limits. The loop can never be unbounded. See `plans/safety_plan.md`.
- Output is always a push to a **work branch**. The agent never touches main; merging is a final gate.

## Safety posture (summary — full detail in plans/safety_plan.md)

Unattended runs require: structured exit signals (the orchestrator decides "done", never agent prose), a circuit breaker, rate and budget caps, branch-only pushes, deny-rules on destructive commands, and isolation (container or constrained worktree) with no real credentials exposed to the loop.

## Self-healing (human-gated)

When review attributes a failure to ambiguity in the harness itself (a stage spec, skill, or hook), the agent files a **system-repair ticket**. A human approves before any harness file is modified. Agents never self-modify the harness mid-run. Tactical (non-structural) lessons go to `progress.txt` instead.

## Directory layout

```
agentic-sdlc/
├── AGENTS.md           # lightweight must-read for every agent
├── architecture.md     # this file
├── plans/              # build plans per subsystem (safety, tickets, hooks, harness, prompts)
├── workflows/          # deterministic .py orchestrators
├── commands/           # reusable lightweight prompts
├── stage_specs/        # per-stage, per-ticket-type contracts
├── skills/             # problem-class templates (Claude Code Skills format)
├── hooks/              # hard guarantees (PreToolUse blockers, Stop checklists, auto-commit)
├── configs/            # model-per-phase config, budgets, per-repo rules
└── observability/      # run logs (hand-off only, deleted post-run), history.md (human-only)
```

## Design principles

1. **Determinism in code, intelligence in prompts.** Control flow, loop bounds, and data flow belong to Python; judgment belongs to the model.
2. **Hard guarantees live in hooks and deny-rules, not prose.** A "non-negotiable" written in markdown is a suggestion; written as a PreToolUse blocker it is a guarantee.
3. **Explicit data flow.** Prompts passed as flags, file paths passed as inputs, structured JSON out of every stage. Tell agents exactly what to run and which tools to use (Claude Code built-ins, software tools like Playwright, or agentic .md tools).
4. **Modular, front-mattered .mds.** Every markdown asset declares what it is for, when to read it, and at which stage — agents load only what the task needs. No giant CLAUDE.md ("loss of middle" problem).
5. **Bounded everything.** Iterations, budgets, learnings files, logs. Append-only artifacts are bugs. Run logs are hand-offs within one run and get deleted after.
6. **Long descriptive names.** Cheap for humans, load-bearing for agents.
7. **Don't rebuild what exists.** Before implementing any tool, check the reference repos listed in the relevant plan file.
8. **Parallelization via git worktrees** when tickets are independent.

## Plan index

| Plan | Owns |
|---|---|
| `plans/safety_plan.md` | Exit gates, circuit breaker, budgets, branching, isolation |
| `plans/tickets_plan.md` | prd.json / state.json / progress.txt schemas, decomposition, self-healing gate |
| `plans/hooks_plan.md` | PreToolUse blockers, Stop checklists, auto-commit/squash, formatting |
| `plans/harness_plan.md` | Orchestrator, headless invocation, status blocks, model config, observability |
| `plans/prompts_plan.md` | Commands, stage specs, skills, stage personas, review breadth |

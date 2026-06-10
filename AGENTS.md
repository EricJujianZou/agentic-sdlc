---
name: agents-readme
description: Mandatory lightweight orientation for every agent instance spawned by this harness. Read this first, then load only what your current stage needs.
read_when: Always, at the start of every run, before any other file.
sdlc_stage: all
---

# AGENTS.md — Read Me First

You are one fresh instance in an agentic SDLC pipeline. You handle **one stage of one ticket**, then you terminate. A deterministic Python workflow spawned you, and it — not you — decides what happens next.

## The system in five lines

1. Tickets live in `prd.json`; the workflow picked one for you. Your inputs are the ticket, `state.json`, and the prompt assets named in your invocation.
2. You execute exactly one stage: plan, implement, test, or review. The contract for your stage is in `stage_specs/`.
3. If the ticket matches a solved problem class, a skill in `skills/` tells you how — check before re-deriving anything.
4. Git is the memory layer. Everything you want a future agent to know must be committed, written to `state.json`/`progress.txt`, or it is gone.
5. You finish by emitting the structured status block your workflow expects. Prose like "done!" is not a completion signal.

## Rules of the road

- **Never push to main.** Work happens on the work branch; merging is a gate you don't control.
- **Stay in scope.** One stage, one ticket. Adjacent problems become new tickets, not side quests.
- **Respect front-matter.** Every .md declares when it should be read. Don't load files outside your stage's needs.
- **Hooks are law.** If a hook blocks an action, that's a design decision, not an obstacle to work around.
- **Bounded learnings.** Append tactical lessons to `progress.txt` (and prune it — keep it under its cap). Durable patterns: propose a skill. Harness ambiguity/bugs: file a system-repair ticket — never edit harness files yourself.
- **Don't rebuild what exists.** Each `plans/*.md` lists reference repos for its subsystem. If you see a missing tool during a run, suggest adopting from those repos in your status block rather than building from scratch.

## Where to look

| Need | File |
|---|---|
| How the whole system fits together | `architecture.md` |
| Your stage's contract | `stage_specs/` |
| A solved problem class | `skills/` |
| Ticket and state schemas | `plans/tickets_plan.md` |
| Why something is blocked / safety rules | `plans/safety_plan.md` |
| Codebase orientation | `commands/PRIME.md` |

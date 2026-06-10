---
name: hooks-plan
description: Hooks subsystem — hard guarantees enforced at the tool-call level. PreToolUse blockers, Stop-hook checklists, auto-commit/squash, formatting. If a rule must never be broken, it lives here, not in prose.
read_when: Building or modifying hooks; deciding whether a rule belongs in a stage spec (guidance) or a hook (guarantee); debugging a blocked tool call.
sdlc_stage: build-time; enforced at every stage at runtime
---

# Hooks Plan

Principle: **prose is a suggestion; a hook is a guarantee.** Any "non-negotiable" found in a stage spec should be promoted into a hook here and demoted to a pointer in the spec.

## 1. PreToolUse blockers (deny-rules)

Block, at the tool-call level:

- `git push` to main / `git merge` into main (branch policy — see `plans/safety_plan.md`)
- Destructive commands: `rm -rf` outside the worktree, `git reset --hard`, `git push --force`, history rewrites
- Edits to harness files (`stage_specs/`, `skills/`, `hooks/`, `workflows/`) during a normal ticket run — these require an approved `system-repair` ticket
- Network calls to anything outside an allowlist during unattended runs
- Reading credential files / env files outside the sanctioned config path

Each blocker returns a one-line reason so the agent can adjust instead of flailing (it also counts toward the circuit breaker's permission-denial threshold).

## 2. Stop-hook completion checklists

On agent stop, verify mechanically before the workflow accepts the stage:

- Status block present and parseable
- Working tree clean (everything committed) on the work branch
- For implement: build passes locally
- For test: test artifacts exist where the stage spec says they should
- progress.txt within its size cap

Failed checklist = stage is not complete, regardless of what the agent said.

## 3. Auto-commit and squash

- **PostToolUse auto-commit**: every file edit gets a micro-commit with a contextual message → fine-grained revert during a run.
- **Stage-boundary squash**: the workflow squashes a stage's micro-commits into one well-named commit (`S-001 implement: <summary>`) — honors the no-redundant-commit-messages rule while keeping in-run granularity.

## 4. Formatting & hygiene

- PostToolUse format-on-edit using the project's formatter (per-repo config in `configs/`).
- Pre-commit/post-commit git hooks remain part of the deterministic harness (lint, type-check) — agents cannot skip them (`--no-verify` is itself blocked).

## Reference repos — adopt before building

| Tool need | Repo | What to take |
|---|---|---|
| Ready-made guardrail hooks, rules-enforced-via-hooks pattern | `rohitg00/awesome-claude-code-toolkit` | 20 hooks, 15 rules; natural-language rules enforced via 17 lifecycle hooks (PreToolUse blocking, Stop checklists, audit trail) |
| Auto-commit per edit, cross-platform installer (Win11) | `rinadelph/rins_hooks` | auto-commit hook with contextual messages; PowerShell-native install; notification hooks |
| Hook patterns & education | `disler/claude-code-hooks-mastery`, official hooks docs | Lifecycle reference, exit-code conventions |
| Broader hook discovery | `hesreallyhim/awesome-claude-code` | Curated hooks section — check before writing any new hook |

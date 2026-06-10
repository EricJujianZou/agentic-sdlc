---
name: handoff-harness-v1
description: Session hand-off for the in-flight harness v1 implementation (tasks 3–5 remaining). Delete after the work completes.
read_when: Resuming implementation of the plans/ subsystems.
sdlc_stage: build-time
---

# Hand-off — harness v1 implementation

## Decisions made by the user (binding)

- Order: schemas-first — tickets → harness → **safety → hooks → prompts** (remaining).
- Reference repos: **fetch & adapt** (shallow clones live in `$env:TEMP\ref-ralph` and `$env:TEMP\ref-ralph-cc`; re-clone if gone).
- Scope: **pragmatic v1** — one ticket end-to-end, attended, on the Win11 host. Defer container isolation, parallel worktrees, full stage_spec × ticket-type matrix.
- Stack: **Python + uv**, hooks as cross-platform **Python scripts** (not PowerShell).
- Stop in a clean committed state whenever context use exceeds ~50%.

## Done (branch `feat/harness-v1`, off `main`)

- `ce9fde9` — Task 1, tickets & state: `adw/tickets.py` (prd schema validation, priority picker, human-gated `system-repair` filing — filed as `blocked`, human flips to `open`), `adw/state.py`, `adw/progress.py` (100-line cap). Seeds: `prd.json`, `progress.txt`, `observability/history.md`.
- `17dc390` — Task 2, harness: `adw/status.py` (status block = only completion signal), `adw/invoke.py` (`claude -p` headless, per-stage `--allowedTools`, timeout reported not raised), `adw/orchestrator.py` (bounded loop; success→next, failure→back to plan, blocked→halt; dual gate = review success + `exit_signal`; pluggable `Breaker` protocol), `adw/runlog.py`, `configs/models.json`, `configs/budgets.json`, `workflows/feat_full_cycle.py`.
- 29 pytest tests green (`uv run pytest -q`).

## Remaining (task list IDs in session task tracker)

1. **Task 4 — safety** (next; do before hooks): implement `adw/safety.py` as the `Breaker` the orchestrator already accepts (`record(state, result) -> halt reason | None`). Counters per `plans/safety_plan.md` §2: 3 no-file-change loops, 5 same-error loops, >70% output decline, 2 permission denials; plus per-ticket token budget from `configs/budgets.json`, 30-min cooldown written to `state.json`, provider 5-hour-limit detection. Wire into `workflows/feat_full_cycle.py` (currently passes no breaker). Note: `StageResult.permission_denials` exists but `invoke.py` never populates it yet — parse denials from the CLI envelope/output when implementing.
2. **Task 3 — hooks** (`plans/hooks_plan.md`): Python hook scripts under `hooks/` + `.claude/settings.json` wiring. PreToolUse deny-rules (push/merge to main, destructive cmds, harness-file edits without approved system-repair ticket, `--no-verify`), Stop checklist (status block parseable, clean tree, `adw.progress.assert_under_cap`), PostToolUse auto-commit. Adapt from `rohitg00/awesome-claude-code-toolkit` and `rins_hooks` (not yet cloned).
3. **Task 5 — prompts** (`plans/prompts_plan.md`): `commands/PRIME.md` + `PLAN/IMPLEMENT/TEST/REVIEW.md` (the workflow composes prompts from `commands/<STAGE>.md` and errors if missing), `stage_specs/*_feat.md` for v1, skills/ scaffold. Every .md needs `name/description/read_when/sdlc_stage` front-matter.

## Gotchas

- `workflows/feat_full_cycle.py` cannot run until Task 5 creates the command files (intentional, fails with a clear message).
- Status-block contract examples live in `plans/harness_plan.md` §2; keep stage_specs' required output format in sync with `adw/status.py`.
- Merge of `feat/harness-v1` to `main` is the human's call — never push/merge to main.
- Delete this file once tasks 3–5 are done.

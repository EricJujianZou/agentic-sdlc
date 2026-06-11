# Ticket backlog

Human-curated backlog. A ticket runs only after it is promoted into
`prd.json` (schema in README.md / `plans/tickets_plan.md`). Keep entries
small enough that one SDLC stage fits in one context window; split
anything that doesn't.

Statuses here are coarse: `idea` → `ready` (criteria written) →
`promoted` (in prd.json; live status tracked there) → `shipped`.

---

## Promoted

*(nothing currently promoted — prd.json has no open stories)*

## Ready

### Bug + trivial workflows — `ready`

`bug_plan_implement_test.py` and `trivial_implement_test.py` are named in
`architecture.md` but don't exist; ticket types `bug`/`chore` are
schema-valid but unrunnable (finding A3). Compose from existing `adw/` pieces.

### Breaker: trip instantly on repeated dead-on-arrival stages — `ready`

Run 2 burned all iterations on identical instant failures (CLI exit≠0,
0 tokens, empty output). Trip after 2 such results regardless of the
same-error threshold, which can never fire before max-iterations under
default budgets (test_run1.md follow-up 1).

### Add "you are headless" rule to stage commands — `ready`

In runs 3–4 agents ended contradictory situations by asking the
nonexistent human a question instead of reporting `blocked` in the
status block; one lost its plan text that way (test_run1.md follow-up 2).

## Ideas

- Enforce or delete `hourly_api_call_cap` in budgets.json (finding A2).
- Fix guard-hook push-to-main regex false positive on branch names
  containing "main" (finding A4).
- Seed first skills after S-001 merges: `static_web_page` (generalize
  from S-001 — review flagged it as a clean first solve),
  `python_module_with_tests` (finding A6 / improvements C5).
- Configure a Playwright MCP server so review lens 3 stops being
  skipped (review suggested it via `suggested_tools` both runs).
- Container isolation for unattended runs (improvements C1 — highest-leverage safety item).
- Backlog runner: outer loop over open stories with cooldown between
  tickets (improvements C6).
- Deterministic test-evidence check in the orchestrator before accepting
  `done` (improvements C3).

## Shipped

### S-001 — Ticket dashboard (replace Notion for viewing tickets) — `shipped` 2026-06-10

Completed by the harness in 1 iteration (run 5), merged to main
(`1d83097`), finalized via `workflows/merge_gate.py`. Run analysis:
`observability/test_run1.md`; durable record: `observability/history.md`.

### Wire run-log cleanup + merge history — `shipped` 2026-06-10

`workflows/merge_gate.py` (human-run, post-merge) now calls
`cleanup_run()` and `append_history_line()` — audit finding A1 closed.
Run it after every merge: `uv run python workflows/merge_gate.py
--ticket S-NNN --summary "what + why"`.

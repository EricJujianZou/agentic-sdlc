# Ticket backlog

Human-curated backlog. A ticket runs only after it is promoted into
`prd.json` (schema in README.md / `plans/tickets_plan.md`). Keep entries
small enough that one SDLC stage fits in one context window; split
anything that doesn't.

Statuses here are coarse: `idea` → `ready` (criteria written) →
`promoted` (in prd.json; live status tracked there) → `shipped`.

---

## Promoted

### S-001 — Ticket dashboard (replace Notion for viewing tickets) — `promoted` / done, awaiting merge gate

**2026-06-10: completed by the harness in 1 iteration (run 5); branch
`adw/S-001` awaits human merge. Verified serving over HTTP. See
`observability/test_run1.md` for the full run log.**

A local, zero-build dashboard so a human can see the backlog and live
ticket state in a browser instead of a Notion board.

- Static HTML + vanilla JS/CSS in `dashboard/`, no frameworks, no build step.
- Reads `prd.json` (live machine state) and renders one card per story:
  id, type, title, priority, status, acceptance criteria; grouped into
  columns by status (open / in_progress / blocked / done).
- Serve from repo root with `uv run python -m http.server 8000` and open
  `http://localhost:8000/dashboard/` (browsers block `fetch` of local
  files over `file://`, so a static server is required — document this).
- Acceptance criteria: see prd.json S-001.

## Ready

### Wire run-log cleanup + merge history — `ready`

`adw/runlog.cleanup_run()` and `append_history_line()` are implemented
and tested but never called (audit finding A1, `plans/improvements.md`).
Add a small human-run merge-gate script that appends the history line
and deletes `observability/runs/<id>/` after merge.

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

*(nothing yet — history lives in `observability/history.md` once wired)*

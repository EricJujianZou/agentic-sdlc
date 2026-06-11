# Ticket backlog

Human-curated backlog. A ticket runs only after it is promoted into
`prd.json` (schema in README.md / `plans/tickets_plan.md`). Keep entries
small enough that one SDLC stage fits in one context window; split
anything that doesn't.

Statuses here are coarse: `idea` → `ready` (criteria written) →
`promoted` (in prd.json; live status tracked there) → `shipped`.

---

## Promoted

### S-001 — Ticket dashboard (replace Notion for viewing tickets) — `promoted`

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

## Ideas

- Enforce or delete `hourly_api_call_cap` in budgets.json (finding A2).
- Fix guard-hook push-to-main regex false positive on branch names
  containing "main" (finding A4).
- Seed first skills after S-001 ships: `static_web_page`,
  `python_module_with_tests` (finding A6 / improvements C5).
- Container isolation for unattended runs (improvements C1 — highest-leverage safety item).
- Backlog runner: outer loop over open stories with cooldown between
  tickets (improvements C6).
- Deterministic test-evidence check in the orchestrator before accepting
  `done` (improvements C3).

## Shipped

*(nothing yet — history lives in `observability/history.md` once wired)*

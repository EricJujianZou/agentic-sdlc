# Ticket backlog

Human-curated backlog. A ticket runs only after it is promoted into
`prd.json` (schema in README.md / `plans/tickets_plan.md`). Keep entries
small enough that one SDLC stage fits in one context window; split
anything that doesn't.

Statuses here are coarse: `idea` → `ready` (criteria written) →
`promoted` (in prd.json; live status tracked there) → `shipped`.

---

## Promoted

All promoted 2026-06-10 as `system-repair` stories (they edit harness
files, which the guard hook only allows on system-repair tickets). Live
status is tracked in prd.json; S-004…S-007 sit at `blocked` per the
human-gate convention — flip to `open` when their turn comes.

- **S-002** — "you are headless" rule in all stage commands — `open`
  (test_run1.md follow-up 2: agents asked the nonexistent human instead
  of reporting `blocked`).
- **S-003** — breaker trips on 2 consecutive dead-on-arrival stages —
  `open` (test_run1.md follow-up 1: run 2 burned all iterations on
  instant failures the same-error rule can never catch).
- **S-004** — bug + trivial workflows (finding A3) — `blocked` until S-002/S-003 ship.
- **S-005** — backlog runner outer loop (improvements C6) — `blocked`.
- **S-006** — GitHub Issues intake + done/blocked notifications (the
  phone-facing taskboard) — `blocked`.
- **S-007** — container isolation for unattended runs (improvements C1)
  — `blocked`; precondition for leaving the system alone.
- **S-009** — CI gate: GitHub Actions `pytest` on every PR + branch
  protection on main — `open` (independent worktree lane; the agent-proof
  correctness gate, outside the stage agents' trust boundary, that makes
  auto-merge defensible). Branch protection is a one-time human repo-admin
  step documented in the ticket, never an agent action.
- **S-010** — deterministic test-evidence re-run in the orchestrator
  before accepting `done` (improvements C3) — `blocked` until the
  workflow-completion path settles (it edits `run_ticket`, overlapping
  S-005/S-006); the in-harness mirror of S-009 and the prerequisite for
  auto-merging trivial tickets.

### Wave 2 — multi-repo + phone-facing operation (promoted 2026-06-18)

The "use this to build my other projects, driven from my phone" wave.
Suggested order S-011 → S-013 → S-014 → S-012. All `blocked` (human-gate
convention; flip to `open` when their turn comes).

- **S-011** — repo-agnostic engine: resolve a target repo from `ADW_REPO` /
  git top-level so the harness can build *other* repos, not just itself —
  `blocked`. The unlock for everything else in this wave.
- **S-013** — `decompose` stage: terse/phone issues auto-expanded into
  acceptance criteria; relax `sync_issues` to accept them — `blocked`.
  Motivated live by issue #16 (quote-bar body → skipped).
- **S-014** — per-stage progress comments on the source GitHub issue so the
  phone gets a running log (S-006 only comments at the terminal outcome) —
  `blocked`. Injects a progress callback into `run_ticket`.
- **S-012** — one-shot `sync_issues`→`run_backlog` runner; **no daemon/cron**
  (per the no-triggers decision), OS-scheduler wiring is a documented human
  opt-in — `blocked`. Worth it only once S-011/13/14 smooth the round-trip.

## Ready

*(empty — everything actionable is promoted)*

## Ideas

- Enforce or delete `hourly_api_call_cap` in budgets.json (finding A2).
- Fix guard-hook push-to-main regex false positive on branch names
  containing "main" (finding A4).
- Seed first skills: `static_web_page` (generalize from S-001 — review
  flagged it as a clean first solve), `python_module_with_tests`
  (finding A6 / improvements C5).
- Configure a Playwright MCP server so review lens 3 stops being
  skipped (review suggested it via `suggested_tools` both runs).

## Shipped

### S-008 — Document stage (post-gate change doc for the merge human) — `shipped` 2026-06-12

Built autonomously by the harness in 1 iteration (attempt 3; attempts 1–2
died on a *contended* provider session limit — a concurrent 5-way
parallel batch, `test_run3.md`, not a harness bug). Squash-merged to main
via PR #9 (`faac430`), finalized via `workflows/merge_gate.py`. 116/116
tests green, re-verified by hand. Run analysis:
`observability/test_run2.md`; new findings A7–A9 in
`plans/improvements.md`. **Caveat:** the document stage's *live* path
(prompt compose → `claude -p` → in-stage git commit) is unexercised — its
first real run is the next ticket after this merge; watch it.

### S-001 — Ticket dashboard (replace Notion for viewing tickets) — `shipped` 2026-06-10

Completed by the harness in 1 iteration (run 5), merged to main
(`1d83097`), finalized via `workflows/merge_gate.py`. Run analysis:
`observability/test_run1.md`; durable record: `observability/history.md`.

### Wire run-log cleanup + merge history — `shipped` 2026-06-10

`workflows/merge_gate.py` (human-run, post-merge) now calls
`cleanup_run()` and `append_history_line()` — audit finding A1 closed.
Run it after every merge: `uv run python workflows/merge_gate.py
--ticket S-NNN --summary "what + why"`.

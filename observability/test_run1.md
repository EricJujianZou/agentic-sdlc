---
name: test-run-1
description: Observation log of the harness's first real ticket (S-001, ticket dashboard) — five runs, four harness bugs, one clean completion. Human-only record.
read_when: Humans evaluating harness reliability or planning v2 fixes. Agents never read this.
sdlc_stage: none (post-run analysis)
---

# Test run 1 — S-001 ticket dashboard (2026-06-10)

First end-to-end exercise of the harness on a real feat ticket:
*"Ticket dashboard: local static page rendering prd.json stories."*
Run 5 completed cleanly (`done` after 1 iteration, branch `adw/S-001`
awaiting the human merge gate; dashboard verified serving over HTTP).
Runs 1–4 each exposed a distinct harness defect, all fixed the same day
(PRs #2–#5). **Every failure was the harness's fault, not the agents'.**

## Run-by-run

| Run | Outcome | Root cause | Fix |
|---|---|---|---|
| 1 | Crash before any stage | `subprocess.run(["claude", ...], shell=False)` can't spawn the npm `.cmd` shim from a bare name on Windows | resolve via `shutil.which` (PR #2) |
| 2 | Burned all 3 iterations on empty plan output, halted | cmd.exe shim mangled the multi-line prompt passed as argv (`error: unknown option '---'`); stderr was discarded so the log showed only "no status block" | prompt via stdin; stderr captured into results/logs (PR #3) |
| 3 | Breaker at plan: 5 permission denials | Three-way contradiction: PRIME/REVIEW order git commands the stage scopes denied; orchestrator left `prd.json` dirty; Stop hook demanded a commit the read-only planner couldn't make; review lens 3 hard-required an unconfigured Playwright MCP | scoped git read rules for plan/review; orchestrator commits its own bookkeeping; stage-aware Stop gate (`ADW_STAGE`); lens-3 fallback (PR #4) |
| 4 | All four stages succeeded, review returned `exit_signal: true` — **then the breaker vetoed the finished ticket** on 3 cumulative denials | `breaker.record` ran before the completion gate; denial threshold hardcoded at 2 and counted cumulatively across stages | completion outranks breaker; `permission_denial_cap` wired to budgets.json, default 10 (PR #5) |
| 5 | **done, 1 iteration** | — | — |

## Where it went off track

- **Run 2 was the worst failure mode: a silent, repeated, instant stall.**
  Three identical iterations of a dead-on-arrival CLI call, zero
  diagnostic output preserved, and the loop happily re-tried. Two
  lessons: (1) never discard stderr; (2) the breaker's `same_error_loops`
  threshold (5) exceeds the default iteration cap (5 vs 3 used here, and
  equal in the default config) — the same-error rule can barely ever fire
  before max-iterations does. **Open item: trip on N identical *instant*
  failures (exit≠0 + 0 tokens) immediately, N=2.**
- **Run 3/4's denials were the permission system *working*** — the agent
  asking for a tool outside its scope and accepting "no". Counting those
  cumulatively against a threshold of 2 made healthy friction fatal.
- **Run 4's false halt** is the subtlest bug: orchestration order made a
  safety counter outrank a satisfied completion gate. Finished work was
  marked `blocked`.

## Where it stalled

- No within-stage stalls or timeouts in any run (15-min stage timeout
  never hit). Stage wall-times were minutes; the visible "stall" pattern
  was always the *loop* re-trying a doomed iteration (run 2).

## Where it was too verbose / off-pitch

- Agent outputs were generally disciplined: implement replied in ~10
  lines + status block; test gave per-criterion evidence (exactly what
  the review spec wants); plan was ~5 KB with explicit AC mapping and a
  risk list — long but load-bearing (run 5's implementer demonstrably
  used Risk 2, the unknown-status fallback).
- The one off-pitch behavior: in runs 3–4, agents hit contradictory
  constraints and ended by **asking the (nonexistent) human a question**
  ("Two ways forward, your call") instead of emitting a `blocked` status
  block. The stage commands should state explicitly: *you are headless;
  nobody will answer; blocked goes in the status block.* Run 3's planner
  also lost its actual plan text that way (the Stop-hook-forced extra
  turn replaced the final message, and only the final message survives).
- Plan stage's "Context" section re-narrates the ticket back (~1
  paragraph of pure recap). Harmless at this size; would trim at scale.

## What worked notably well

- **Structured status blocks**: every successfully-launched stage ended
  with a parseable block; prose never leaked into control flow.
- **Honest self-limitation**: run-3's planner correctly refused to
  overstep its read-only remit; run-4/5's reviewer explicitly flagged
  the skipped visual lens and suggested `playwright` via
  `suggested_tools` instead of bluffing a pass.
- **Micro-commit hook**: `adw auto: write dashboard/index.html` /
  `... tests/test_dashboard.py` — clean, attributable history on the
  work branch with zero agent effort.
- **Quality of the artifact**: XSS-safe rendering (`textContent` only),
  defensive guards, unknown-status fallback, responsive 4→2→1 grid,
  error banner — verified by me over HTTP post-run. The review's
  "candidate for a `skills/` entry" call is right: this is the seed for
  a `static_web_page` skill.

## Costs (observed)

Run 4: ~18k tokens billed across 4 stages; run 5 similar. Runs 1–3 were
near-free failures (crash, empty calls, one plan stage). Per-ticket
token budget (2M) was never within two orders of magnitude.

## Follow-ups filed

1. Instant-failure trip rule for the breaker (see above) — task.md.
2. "You are headless" line in all `commands/*.md` stage prompts.
3. Seed `skills/static_web_page` from S-001 (after merge).
4. Configure a Playwright MCP so review lens 3 stops being skipped.
5. Pre-existing backlog: wire `cleanup_run`/`append_history_line` at the
   merge gate; bug/trivial workflows; `hourly_api_call_cap` unwired.

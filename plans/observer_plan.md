---
name: observer-plan
description: Design of the observer stage — the whole-system self-heal lens that runs on a non-done ticket, classifies ticket- vs harness-level, and surfaces a human-gated suggestion.
read_when: Working on self-healing, the observer stage, or why a non-done ticket posts a self-heal/needs-clarification label.
sdlc_stage: observe
---

# Observer agent — self-heal lens

## Problem

Context isolation gives each phase agent only a *local* view by design, so it
can see "this test failed" but never "this is the third ticket the same spec
ambiguity has broken." That cross-ticket, whole-system pattern is structurally
invisible to a fresh-per-stage agent — and nobody else held that lens. The
`system_repair_suggested` flag existed but nothing acted on it, so self-healing
meant a human reading run logs.

## Approach

Deterministic trigger → read-only judgment → human-gated output.

1. **Trigger** (deterministic): in `run_one_story`, on any non-done outcome
   (`blocked`/`halted`, including the decompose-block path), the orchestrator
   invokes the observer **once**. Gated by `budgets.observer_enabled`.
2. **Observer stage** (`commands/OBSERVE.md` + `stage_specs/observe.md`):
   read-only tools only (`STAGE_TOOLS["observe"]` = Read/Glob/Grep + read-only
   git). Given the ticket, the run's stage outputs, `state.last_failure`, and
   the work-branch diff, it classifies the root cause:
   - **ticket** — specific to this request (ambiguous/contradictory/hard) → a
     human clarifies the ticket.
   - **harness** — a spec/command/hook/config that would mislead *any* ticket →
     a change to the system. It proposes a repair (title/description/evidence).
3. **Orchestrator consumes** (deterministic, `_observe_and_report`): on
   `harness`, post the proposed repair as an issue comment + the
   `self-heal-suggested` label; on `ticket`, post the diagnosis + the
   `needs-clarification` label. Best-effort throughout — never raises, never
   changes the ticket's outcome.

## Why it's safe

- Runs **only on a non-done outcome** → cost bounded by failure frequency.
- **Read-only, single-shot** → it proposes, never edits/commits/files. The one
  place we deliberately spend big (whole-repo) context, fenced.
- Capped by `stage_timeout_minutes` (invoke caps by timeout, not tokens).
- Non-determinism never reaches authority: the observer only *suggests*; the
  deterministic orchestrator does the gated surfacing, and the human decides.

## Scope deferred (intentional)

**Auto-filing the system-repair ticket is NOT wired.** `prd.json` status lives
on the *work branch* (a blocked ticket's branch may never merge), and a
system-repair filed as a GitHub issue would sync back as an *open* story and
bypass the human gate. Both need the "where does prd.json state live across
branches" question solved first. So v1 surfaces the full proposal in the issue
comment — formatted so the human files/opens it in one paste — instead of
auto-creating it. `tickets.file_system_repair_story` remains the helper for
when filing is wired (it already lands `status=blocked`, human-gated).

## Files

- `commands/OBSERVE.md`, `stage_specs/observe.md` — prompt assets.
- `adw/state.py`, `adw/invoke.py` — register the `observe` stage + read-only tools.
- `adw/orchestrator.py` — `run_observer`, `parse_observer_proposal`, `ObserverResult`.
- `adw/workflow_runner.py` — `_observe_and_report`, `_format_repair_comment`,
  `_post_observer`, the `self-heal-suggested` / `needs-clarification` labels, and
  the wiring in both non-done paths of `run_one_story`.
- `configs/models.json` (observe → opus), `configs/budgets.json`
  (`observer_enabled`).

## Tests

`tests/test_observer.py`: proposal parsing (harness/ticket/invalid),
`run_observer` (success/non-success/no-status), `_observe_and_report`
(harness→self-heal label, ticket→clarify label, observer-problem→silent,
plain-story→no-op), and the OBSERVE.md status contract. No live agents/GitHub.

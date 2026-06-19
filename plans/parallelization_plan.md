---
name: parallelization-plan
description: Design for #4 — parallel ticket execution via git worktrees (Tier 1). One blocked ticket halts only its worktree, not the whole backlog. No dependency analysis yet.
read_when: Building or reviewing parallel backlog execution, the parent/worker split, or worktree isolation.
sdlc_stage: all
---

# Parallelization plan (#4) — parallel worktrees, Tier 1

## Goal & non-goals

**Goal:** run up to *N* independent open tickets concurrently, each isolated in
its own `git worktree` + `adw/<id>` branch, so one blocked ticket halts only its
worktree instead of stalling the whole backlog (today's sequential
stop-on-block).

**Non-goals (Tier 1):**
- No dependency analysis (no `depends_on`) — conflicts between two tickets that
  touch the same files surface at the human merge gate. Declared deps are
  Tier 2.
- No container isolation — worktrees only (the `isolation.py` docker path stays
  orthogonal).
- Parallel is **opt-in**; sequential remains the default until proven.

## Core problem: shared mutable state

`prd.json`, `state.json`, and the single working tree cannot be written
concurrently. The whole design is a **parent/worker split**:

- **Parent coordinator** owns *all* `prd.json` reads/writes, story selection,
  the batch cooldown check, result reconciliation, `_notify_github` / relabel /
  observer, and the worktree lifecycle.
- **Worker** runs one ticket's pipeline inside its own worktree, returns a
  `TicketOutcome`, and touches **no** shared state.

## Data flow (one batch)

1. Parent: **cooldown check once** — if the circuit is in cooldown, abort the
   batch (workers never override it).
2. Parent: load `prd.json`, pick up to `max_parallel` open stories by
   `(priority, id)`.
3. Parent: for any criteria-less story, **run decompose serially in the
   parent** (read-only; persists criteria, or drops the ticket as blocked +
   notifies). Keeps workers fully write-free and preserves decompose's
   block-on-vague behavior.
4. Parent: mark all survivors `in_progress`, commit once.
5. Parent: per story, `git worktree add <root>/<id> -b adw/<id> main`, spawn a
   **worker thread** (work is subprocess-bound — `invoke_stage` — so threads
   give real parallelism without process overhead).
6. **Worker(story, worktree_dir):** runs `run_ticket` with `cwd` + `state_path`
   scoped to the worktree. Per-stage progress comments still fire (per-issue,
   concurrency-safe). **No `prd.json` writes, no notify.** Returns the outcome.
   A worker exception is caught and turned into a blocked outcome, so one
   failure never aborts the batch.
7. Parent: as workers finish, **serially** apply outcomes to the canonical
   `prd.json` (done/blocked), commit, push the branch, then run
   `_notify_github` + relabel + observer (serialized — the observer spawns an
   agent; running N at once multiplies cost).
8. Parent: remove worktrees and `git worktree prune`, in a `try/finally` so
   cleanup survives a crash.

## Locked decisions

Threads · `max_parallel = 3` · opt-in `--parallel` · parent owns all
`prd.json` writes · parent-level cooldown check.

## Hard parts / edge cases

1. **prd.json ownership** — ONLY the parent reads/writes it; workers get the
   `Story` object in memory. The existing `run_one_story` does prd flips
   (in_progress at start, done/blocked at end) and decompose persistence — all
   of that moves OUT of the worker into the parent. Decompose is the subtle one
   (it writes prd mid-run today): the parent runs it before dispatch so workers
   only ever see fully-specified stories.
2. **Worktree + branch** — `git worktree add` creates `adw/<id>` in the
   worktree; the auto-commit hook commits there. Worktrees share the object
   store + refs, so the parent can push the branch after the worker returns.
3. **state.json per worktree** — `run_ticket` already takes an explicit
   `state_path`; the worker uses a worktree-local one. The worker's `invoke`
   closure passes `cwd = worktree_dir` (not `paths.target_root()`).
4. **Path resolution** — `configs/` and `commands/` resolve from the engine
   (shared, read-only); `budgets`/`models` are read once by the parent and
   passed to workers as dicts. Workers never read the worktree's `prd.json`.
   The breaker's cooldown write lands in the *worker's* state.json; the parent's
   batch cooldown reads the target's main state.json (workers never write it).
5. **Concurrent git** — safe across worktrees on different branches; do not run
   `gc` concurrently. Each worktree's auto-commit touches only its own index.
6. **runs/ logs** — `runlog.run_dir(story.id)` is already unique per ticket;
   concurrent writes hit different dirs.
7. **Crash / cleanup** — `try/finally` per worktree + `git worktree prune` at
   batch start and end; a hard crash leaves an orphan dir that prune + rm clears.
8. **Failure isolation** — wrap each worker so an exception becomes a blocked
   outcome; the batch always completes and the parent reconciles.
9. **Post-processing serialization** — prd writes, relabel, and observer touch
   shared things or spend agent cost, so the parent does them serially.

## Files

- **`adw/worktrees.py`** (new): `add_worktree` / `remove_worktree` / `prune`,
  plus a crash-safe context manager.
- **`adw/workflow_runner.py`**: factor `run_one_story` into (i) the per-ticket
  **work** (worktree-scoped, no shared writes) and (ii) the **coordination**
  (prd flips, decompose persistence, notify, relabel, observer), so the
  sequential and parallel paths share one implementation.
- **`workflows/run_backlog_parallel.py`** (new) or a `--parallel` flag on
  `run_backlog`; `poll_once.py` threads the flag through.
- **`configs/budgets.json`**: `max_parallel`.

## Incremental rollout (~3 PRs)

- **PR A** — `adw/worktrees.py` + tests (temp-repo create/remove/prune,
  cleanup-on-exception). No behavior change.
- **PR B** — refactor `run_one_story` into work/coordination halves; the
  sequential path calls them back-to-back. The existing suite must stay green,
  proving the split is behavior-preserving *before* concurrency lands.
- **PR C** — the parallel coordinator + `--parallel` + `max_parallel` + tests
  with a stub worker: N picked by priority, all `in_progress` up front, outcomes
  reconciled serially, worktree lifecycle, one failing worker doesn't abort the
  batch, cooldown checked once.

## Tests

- worktrees: temp git repo — add/remove/prune, idempotent cleanup, removal even
  on exception.
- coordinator: stub worker — selection, up-front in_progress marking, serial
  reconciliation, worktree lifecycle, exception isolation, single cooldown check.
- regression: the sequential path is unchanged (the current suite stays green).

## Risks & mitigations

- Cost N× concurrent agents → `max_parallel` + per-ticket token budgets.
- Merge conflicts at the gate → human merge resolves; Tier 2 `depends_on`
  reduces later.
- Orphan worktrees → `try/finally` + `git worktree prune`.
- Shared-state races → parent-only `prd.json` writes, per-worktree `state.json`,
  serialized post-processing.

## Open questions (decide before PR C)

1. **Worktree root** — sibling dir outside the repo (`../.adw-worktrees/<id>`,
   leaning here — zero chance of polluting status/hooks) vs inside
   (`.adw/worktrees/`, gitignored).
2. **Decompose location** — in the parent before dispatch (leaning here — keeps
   workers write-free) vs worker-returns-criteria for the parent to persist.
3. **`--parallel` scope** — expose on `poll_once` (the scheduled entry) now, or
   only on `run_backlog` until proven.

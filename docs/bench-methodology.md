# Benchmark Methodology — Scaffolding vs. No-Scaffolding (2026-07-25)

Context: a YC talk claim (Boris Cherny, Claude Code) that newer frontier models
can run long-horizon agent work with no scaffolding, and that harness code
should shrink with every model release. This repo is built on the opposite
thesis. Instead of arguing, we ran a controlled experiment. This doc records
the methodology; results and raw data live on the `bench/base` branch
(`bench/RUN.md`, `bench/results/`).

## What a "task battery" is

A battery is a fixed, ordered set of tasks that every subject completes under
identical conditions, so outcome differences can only come from the variable
under test. Ours is 10 sequential coding tasks (T01-T10) against one small
codebase, `ledgerlite` — a deliberately boring expense-tracker library
(~140 lines: data model, JSON storage, reports, CLI). Boring is the point: no
task is intellectually hard. The battery tests whether an agent *stays
coherent across a sequence*, not whether it can solve puzzles.

## Experiment design: one variable, everything else pinned

Classic A/B structure:

- **Same model, same repo, same 10 task specs, same tests, same starting
  commit** for all four cloud sessions.
- **The only variable is scaffolding.** Arm A got a written protocol
  (`bench/protocol_armA.md`): work one task at a time, never read ahead, keep
  working memory in an external state file capped at 60 lines, run the full
  regression suite before every commit, one commit per task. Arm B got all 10
  specs in a single prompt and ran from a branch (`bench/base-noscaffold`)
  where every scaffolding file (AGENTS.md, CLAUDE.md, stage specs, skills,
  even Arm A's protocol) was deleted, so it couldn't absorb the discipline by
  reading the repo.
- **n=2 per arm** to catch a fluke run in either direction.
- **Metrics were pre-registered**: written into `bench/RUN.md` and committed
  *before* any session launched, so the goalposts couldn't move after seeing
  results.

## KPIs

1. **Per-task pass rate (primary).** Each task has its own test file, written
   before the runs and locked. A task passes only if its entire file passes —
   no partial credit.
2. **Regressions (the context-rot smoking gun).** A regression is a task that
   passed at some intermediate commit but fails at the final state, meaning
   later work silently broke earlier work. This is the specific failure mode
   the "no scaffolding needed" claim has to survive.
3. **Context-rot curve.** Failure rate plotted against task position. If
   quality degrades as the session's context fills, later tasks fail more.
4. **Integrity.** SHA-256 manifest of every test and spec file
   (`bench/test_manifest.json`), checked at grading. An agent that "fixes" a
   failing test by editing the test gets caught, not credited.
5. **Scope discipline.** `git diff` against the starting commit; any changed
   file outside the allowed paths is a violation.
6. **Process shape (descriptive).** Wall time, diff size, commit granularity.

## How measurement worked

Trust-nothing grading. Sessions self-reported, but every number came from
re-running `bench/grade.py` locally on their pushed branches. The `--replay`
mode is the key instrument: it checks out **every commit** into a temporary
git worktree and runs all 11 test files there, producing a per-commit
pass/fail matrix — a time-lapse of correctness across the whole run. That is
what lets you *see* a regression rather than infer it.

## The traps: why the tasks interlock

A battery of 10 independent tasks cannot detect context rot — nothing later
touches anything earlier. So the tasks share state and escalate:

- **T01 (categories)** threads a new field through the data model, storage
  format, and CLI. Every later task depends on it; get it wrong and the
  damage compounds.
- **T03 (hidden bug)** is a planted defect: dates like `2026-1-5` (unpadded)
  silently vanish from monthly reports because the code does naive
  string-prefix matching and string sorting. The spec is written as a *user
  bug report* — symptom only, no file or line. The agent has to diagnose, not
  just patch where it is told.
- **T06 (multi-ledger refactor)** changes the storage file format to hold
  multiple named ledgers while staying backward compatible with the old
  single-ledger JSON from T01-T05. A classic real-world migration: the
  easiest wrong implementation breaks everything already saved.
- **T08 (float to integer cents)** is the cross-cutting one: money
  representation changes internally across the entire codebase while the
  public API stays float-compatible. Every earlier feature — totals, budgets,
  CSV export, summaries — touches money. A careless sweep here is exactly how
  a long-context agent quietly breaks task 2 while doing task 8.
- **T10 (undo)** requires hooks in every mutating operation added across all
  nine prior tasks, forcing the agent to correctly recall the full API
  surface it built.

## Threats to validity (reported, not hidden)

- The design biases *against* the scaffolding thesis in one way: Arm A
  simulates fresh-context stages inside a single session rather than truly
  separate processes, so a scaffolding win would have been conservative.
- n=2 per arm; one model (Devin's), not Opus 5 specifically.
- Tests are visible to agents (tamper-detected via manifest, not hidden).

## Outcome (summary; full numbers on `bench/base`)

All four sessions: 11/11 test files, zero regressions, zero tampering. A tie —
the unscaffolded arm was slightly faster with slightly smaller diffs. At this
scale (10 tasks, ~250 changed lines, ~5-7 minutes of agent time) the run
never saturated a context window, so it *bounds* the no-scaffolding claim
rather than refuting or confirming it. Round 2 needs a battery long enough to
saturate: 50+ tasks, a larger codebase, or real SWE-bench instances.

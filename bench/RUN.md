# Benchmark Run Log — Scaffolding vs. No-Scaffolding

Motivation: test the claim (Boris Cherny, YC talk, 2026-07-25) that frontier
models can run long-horizon agent work "with no scaffolding". Counter-thesis
(this repo): context discipline — fresh context per task, externalized state,
per-task regression gates — measurably beats one free-form long session,
because of context rot.

## Design

- Target: `bench/target/ledgerlite` (small stdlib Python package).
- Battery: 10 sequential, interlocking tasks (`bench/tasks/T01..T10.md`).
  Cross-cutting tasks (T06 multi-ledger refactor, T08 money-to-cents) are
  designed so sloppy later work plausibly breaks earlier features.
- Grader: `bench/grade.py` — per-task pass/fail, test-tamper detection
  (SHA256 manifest), scope-violation detection, and `--replay` (per-commit
  pass matrix = regression timeline).

## Arms (4 cloud Devin sessions, same model, same tasks)

| Session | Branch | Base | Protocol |
|---|---|---|---|
| armA-1 | `bench/armA-1` | `bench/base` | `bench/protocol_armA.md` (scaffolded: one task at a time, state file, regression gate, commit per task) |
| armA-2 | `bench/armA-2` | `bench/base` | same |
| armB-1 | `bench/armB-1` | `bench/base-noscaffold` | none — all 10 tasks in one prompt, "just do them" |
| armB-2 | `bench/armB-2` | `bench/base-noscaffold` | same |

`bench/base-noscaffold` = `bench/base` minus repo scaffolding files
(AGENTS.md, CLAUDE.md, stage_specs/, skills/, protocol_armA.md) so Arm B
sessions can't absorb the harness discipline by osmosis.

## Metrics

1. Final per-task pass rate (primary).
2. Regressions: tasks passing at an intermediate commit but failing at HEAD
   (via `--replay`; Arm B may have few commits — that itself is data).
3. Failure rate vs. task position (context-rot curve).
4. Tamper/scope violations.

## Grading (do this when runs finish)

From repo root, for each arm branch:

    git fetch origin
    git checkout bench/<branch>
    uv run python bench/grade.py --out bench/results/<branch>.json
    uv run python bench/grade.py --replay --out bench/results/<branch>-replay.json

Trust only locally re-run grades, not the sessions' self-reports.

## Results (run of 2026-07-25, graded locally 2026-07-26)

All four sessions completed. Grades below are independent local re-runs
(`bench/results/local_*.json`, `replay_*.json`), not session self-reports.

| Arm | Branch | Final pass | Regressions (replay) | Tampering | Commits | ledgerlite diff | Wall time |
|---|---|---|---|---|---|---|---|
| A (scaffolded) | armA-1 | 11/11 | 0 | none | 10 + report | +269/-26 | ~7 min |
| A (scaffolded) | armA-2 | 11/11 | 0 | none | 10 + report | +238/-24 | ~7 min |
| B (unscaffolded) | armB-1 | 11/11 | 0 | none | 1 + report | +241/-25 | ~5 min |
| B (unscaffolded) | armB-2 | 11/11 | 0 | none | 1 | +215/-24 | ~5 min |

Arm A replay timelines are perfect staircases: each commit adds exactly its
task, nothing ever breaks. Arm B's single-commit shape means no mid-run
timeline exists (itself a difference: no checkpoints to bisect if something
had gone wrong). The scope "violations" flagged on Arm B branches are the
scaffolding files deliberately deleted in `bench/base-noscaffold`, not agent
misbehavior.

**Conclusion: a tie at this scale.** 10 small interlocking tasks (~250 LOC of
edits, ~5-7 min of agent time) sit well below the context-rot horizon of a
current frontier agent. This run does not refute the no-scaffolding claim —
it bounds it: the interesting question is where the horizon is. Next
iteration: a battery long/large enough that a single session's context
actually saturates (50+ tasks, larger codebase, or real SWE-bench instances).

## Known threats to validity (say these in the post)

- n=2 per arm; single model (Devin's), not Opus 5 specifically.
- Both arms run inside one session each; Arm A *simulates* fresh-context
  stages via protocol rather than truly separate processes — this biases
  toward the null, so a positive result is conservative.
- Tests are visible to agents (tamper-detected, not hidden).

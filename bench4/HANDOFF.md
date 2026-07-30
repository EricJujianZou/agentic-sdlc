# Bench4 Handoff — Round 4: Contamination-Free Scaffolding Benchmark on Claude Opus 5

You are the constructing/orchestrating agent for benchmark round 4. Read this
whole file before doing anything. The experiment must be **pre-registered**:
every design artifact (tasks, tests, manifest, RUN.md) is committed and pushed
BEFORE any benchmark session launches. Nothing about the design may change
after the first launch.

## Context: why round 4 exists

The repo tests a claim from a YC talk (Boris Cherny, Claude Code): newer
frontier models can run long-horizon agent work with **no scaffolding**, and
harness code should shrink with every model release. Rounds 1–3 (see
`bench/RUN.md` on `bench/base`, `bench2/RUN.md` on `bench2/base`,
`bench3/RUN.md` on `bench3/base`) ran the scaffolding-vs-none A/B on **Devin's
model**:

- Round 1 (custom 10-task battery, `ledgerlite`): tie — battery too small to
  saturate context. Bounded the claim, didn't test it.
- Round 2 (20× SWE-bench Verified): fresh-context 88% vs one-long-session 77%
  (p=0.039, 3 replicates); 3/3 fabricated timing reports in the unscaffolded
  arm; but memorized instances solved too fast to pressure context.
- Round 3 (20× SWE-bench Verified "1–4 hour" tier): replicate 1 flipped
  direction (A 16/20, B 17/20); replicates 2–3 aborted when Devin credits died
  (see `bench3/RUN.md`, aborted armB-2 with fabricated meta timestamps).

Round 4 fixes the two validity gaps at once:

1. **Model.** The claim is about Claude/Opus-class models. Round 4 runs on
   **Claude Opus 5** (`claude-opus-5`), pinned for every session in both arms,
   via Claude Code cloud sessions.
2. **Contamination.** Opus 5's knowledge cutoff is **May 2026**. SWE-bench
   Verified is fully inside training data. Verified alternatives were checked
   on 2026-07-30 and are all stale: SWE-bench-Live has zero instances created
   after Jan 2026 (test/full/MultiLang splits queried via HF datasets-server);
   SWE-rebench has zero after Oct 2025. Therefore round 4 uses a **freshly
   generated custom battery** that cannot exist in any training set, scaled to
   the size round 1's conclusion said was needed (50+ tasks).

A regression instrument matters because independent SWE-bench instances
cannot detect cross-task regressions (task 14 can't break task 3 in a
different repo). Interlocking tasks in one codebase can — that is the
context-rot smoking gun (see round-1 methodology, `docs/bench-methodology.md`
if present, else `bench/RUN.md`).

## Design spec

### Target codebase: `stockroom` (generate fresh — do NOT reuse ledgerlite)

A deliberately boring inventory/order-management library + CLI, pure Python
stdlib, ~800–1200 lines to start: data model (items, suppliers, orders),
JSON file storage, reports (stock levels, reorder suggestions, order
history), CSV import/export, CLI. No task should be intellectually hard; the
battery tests sequential coherence, not puzzle-solving. Write it yourself,
from scratch, with a few latent seams the tasks will exploit (naive string
date handling, float money, single-file storage) — mirroring round 1's traps.

### Battery: 50 sequential tasks (T01–T50), interlocking

Follow the round-1 trap taxonomy, scaled up. Every later task must depend on
state from earlier ones. Include, spread across the sequence:

- **Threading tasks** (like round-1 T01): new fields threaded through model +
  storage + reports + CLI; later tasks depend on them.
- **Hidden-bug tasks** (like T03): planted defects specced as user bug
  reports — symptom only, no file/line. At least 4, one past position 35.
- **Migration tasks** (like T06): storage format changes that must stay
  backward compatible with files written by earlier tasks. At least 3.
- **Cross-cutting sweeps** (like T08): representation changes (float→integer
  cents; naive dates→ISO; single ledger→multi-warehouse) touching every
  earlier feature while keeping public API compatible. At least 3, positioned
  in the back half where context is fullest.
- **Recall tasks** (like T10): features requiring hooks in every mutating
  operation added so far (undo, audit log, event bus). At least 2, near the
  end.

Each task gets: a spec file `bench4/tasks/T<nn>.md` (written as a user
request, not implementation instructions) and a locked test file
`bench4/tests/test_T<nn>.py`. A task passes only if its whole test file
passes. Tests are written before any run and hashed into
`bench4/test_manifest.json` (SHA-256 of every test + spec + the starting
codebase); grading verifies the manifest, so test tampering is caught, not
credited.

### Arms (identical to rounds 1–3 in structure)

- **Arm A (scaffolded, fresh context):** one cloud session per task.
  Protocol file `bench4/protocol_armA.md` (adapt round 1's
  `bench/protocol_armA.md`): work one task only, never read ahead, external
  state file `bench4/state.md` capped at 60 lines is the ONLY memory carried
  between sessions, full regression suite (`pytest bench4/tests/ -x` over all
  unlocked-so-far tests) before commit, one commit per task, push, stop.
- **Arm B (unscaffolded, one long session):** all 50 specs available, one
  session does everything, launched from branch `bench4/base-noscaffold`
  where ALL scaffolding files are deleted (CLAUDE.md, AGENTS.md, commands/,
  stage_specs/, skills/, plans/, Arm A's protocol, this HANDOFF, RUN.md — same
  strip list as `bench3/base-noscaffold`, commit c4b0a36 shows the pattern).
  Kickoff mirrors `bench3/prompt_armB.md`: solve all tasks in order, "work
  through the list however you see fit."
- **Model:** `claude-opus-5` pinned in EVERY session, both arms (in cloud
  sessions pass `/model opus` as an argument, or pin via the launch config).
  Default effort; do not tune per-arm. Any session that ran on a different
  model is discarded and relaunched, documented in RUN.md.
- **Replicates:** pre-register n=3 per arm; run replicate 1, grade, then
  decide 2–3 by budget. Arm B orderings: forward, reverse, forward (as
  round 3).

### Metrics (inherited from round 1 + round 2/3 additions)

1. Per-task pass rate (primary), whole-test-file, no partial credit.
2. **Regressions**: task passing at an intermediate commit but failing at
   final state (`grade.py --replay`: check out every commit in a temp
   worktree, run all 50 test files, per-commit pass/fail matrix).
3. Positional decay: failure rate vs task position (this is H2; 50 tasks on
   one growing codebase is the first battery that can actually show it).
4. Integrity: manifest check + meta-vs-commit timestamp consistency (H3 —
   rounds 2/3 caught fabricated self-reports in Arm B every time; keep
   per-task `meta.json` with started_at/finished_at/self_assessment and
   diff them against commit times at grading).
5. Scope discipline: diff vs allowed paths.
6. Process shape: wall time, tokens if visible, commit granularity.

### Pre-registration order (strict)

1. Build `stockroom` + 50 specs + 50 test files + manifest + `grade.py` +
   protocol/prompt files on branch `bench4/base`. Sanity-check: a reference
   solution direction exists for every task (you may write and then DELETE
   scratch solutions; only tests are committed), and the T00 starting state
   passes an empty-battery smoke test.
2. Write `bench4/RUN.md`: hypotheses (H1 scaffolding gap, H2 positional
   decay, H3 integrity), arms table, metrics, grading commands, this model
   pin, replicate plan. Commit + push `bench4/base`.
3. Create `bench4/base-noscaffold` (strip scaffolding), commit + push.
4. Only THEN launch anything.

## Orchestration & runs

- Runs are Claude Code **cloud sessions** on the owner's subscription.
  From a local session, spawn remote agents (Agent tool with remote
  isolation / `&`-launch) or have the owner launch from claude.ai/code; each
  gets a kickoff naming its run id, branch (`bench4/armA-1-T<nn>` /
  `bench4/armB-1`), and ordering. Cloud sessions clone this repo — branches
  must be pushed first.
- **Quota timing:** owner's weekly reset was ~6h away at 2026-07-30 (evening
  ET). Sequence so the long Arm B session cannot die mid-run: Arm A sessions
  (independently relaunchable per task) may run pre-reset; start each Arm B
  session only on fresh weekly quota. A quota-killed Arm B session is
  discarded and relaunched clean (documented in RUN.md) — a resumed session
  is not the "one continuous session" treatment. This exact failure aborted
  Devin armB-2 in round 3; don't repeat it.
- Grading is local and free (pytest + git worktrees, no docker).
- Rough budget (API-equivalent): Arm A ≈ 50 short sessions × ~$1–3;
  Arm B ≈ one long session, hours, likely $30–100 as context grows.
  Replicate ≈ $100–250 equivalent — several times cheaper than the SWE-bench
  round, and mostly post-reset.

## Threats to validity (report, don't hide — carry into RUN.md)

- Custom battery = single codebase, single style; generalization limited.
- Constructor and subjects are both Claude models: the battery author is a
  Claude model testing Claude. Mitigations: tasks + tests locked and hashed
  before any run; grading is mechanical (pytest replay); publish everything.
- Cloud-session harness itself is scaffolding neither arm can shed; the
  manipulated variable is repo-level scaffolding + session structure, same
  as rounds 1–3.
- Arm A protocol simulates staged fresh-context work; conservative in the
  same direction as round 1.

## Recovery / continuity

If your session dies: everything committed+pushed on `bench4/base` is the
state. Re-read this file and `bench4/RUN.md`, check which branches exist
(`git branch -r | grep bench4`), and resume at the first missing artifact.
Never edit specs/tests after any session has launched; if a design flaw is
found post-launch, abort the replicate, document in RUN.md, bump to a new
pre-registered revision.

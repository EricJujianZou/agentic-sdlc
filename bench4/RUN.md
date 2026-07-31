# Benchmark Round 4 Run Log — Contamination-Free 50-Task Battery on Claude Opus 5

Round 3 (`bench3/RUN.md`) left two validity gaps: the model (Devin's, not the
Claude/Opus-class models the original no-scaffolding claim was about) and
contamination (SWE-bench Verified is inside every frontier model's training
data; checked 2026-07-30, no public live benchmark has instances newer than
Opus 5's May 2026 cutoff — SWE-bench-Live's newest are Jan 2026, SWE-rebench's
Oct 2025). Round 4 closes both: **Claude Opus 5, pinned, both arms**, on a
**freshly generated 50-task interlocking battery** (`stockroom/`) that cannot
exist in any training set, scaled to the size round 1 said was needed to
saturate a session's context.

Unlike independent SWE-bench instances (which cannot detect cross-task
regressions), all 50 tasks share one codebase and interlock: threading tasks,
symptom-only hidden-bug reports, backward-compatible storage migrations,
cross-cutting representation sweeps (money, dates, storage layout), and
capstone recall tasks requiring the full accumulated API surface.

## Hypotheses (pre-registered)

- **H1 (scaffolding gap):** the fresh-context arm (A) outscores the single
  long session (B) on final per-task pass rate.
- **H2 (positional decay):** Arm B's failures cluster toward later task
  positions; Arm A's do not.
- **H3 (integrity):** Arm B produces fabricated/unverifiable self-reports
  (meta timestamps inconsistent with commit times); Arm A does not.
  (Rounds 2 and 3 observed this in every unscaffolded replicate.)
- **H4 (regressions):** Arm B produces more replay regressions (task passed
  at an intermediate commit, fails at final state) than Arm A.

## Design

- Target: `stockroom/` (stdlib-only Python inventory library + CLI,
  ~1000 lines at base), generated fresh 2026-07-30/31 for this round.
- Battery: `bench4/tasks/T01..T50.md`, locked tests
  `bench4/tests/test_T01..T50.py` + schema fixtures, all SHA-256-hashed in
  `bench4/test_manifest.json` before any run. A task passes only if its
  whole test file passes. `pip install pytest` if missing.
- Model: **`claude-opus-5`** pinned in every session, both arms, default
  effort. Any session that ran on another model is discarded and relaunched
  (documented here).
- Sessions are Claude Code cloud/background agent sessions on the owner's
  subscription.

## Arms

| Run | Branch(es) | Protocol |
|---|---|---|
| armA-1 | `bench4/armA-1` | 50 sequential FRESH sessions, one per task, each following `bench4/protocol_armA.md`; session N+1 starts from session N's pushed commit |
| armB-1 | `bench4/armB-1` | ONE session, all 50 tasks, forward order, from `bench4/base-noscaffold`, kickoff `bench4/prompt_armB.md` |
| armA-2 / armB-2 (adaptive) | as above | armB-2 reverse ordering |
| armA-3 / armB-3 (adaptive) | as above | armB-3 forward ordering |

`bench4/base-noscaffold` = `bench4/base` minus all scaffolding (CLAUDE.md,
AGENTS.md, ONBOARDING.md, architecture.md, commands/, stage_specs/, skills/,
plans/, task.md, progress.txt, claude-code-harness-repos.md, docs/,
bench4/HANDOFF.md, bench4/RUN.md, bench4/protocol_armA.md, prior bench*/
directories) so Arm B cannot absorb the discipline by reading the repo.

Replicates 2-3 run only if budget allows, graded replicate-by-replicate.
An interrupted Arm B session is discarded and relaunched clean — a
resumed session is not the one-continuous-session treatment (this rule
exists because Devin armB-2 died mid-run in round 3).

## Metrics (all computed locally by `bench4/grade.py`; self-reports are data, not grades)

1. Final per-task pass rate (primary, H1).
2. Replay regressions via `--replay` per-commit matrix (H4).
3. Failure rate vs task position (H2), Arm B fwd vs rev orderings.
4. Integrity: manifest tamper check + per-task `meta.json` timestamps vs
   commit timestamps (H3).
5. Scope violations (files outside `stockroom/`, `bench4/results/`,
   `bench4/state*`). Known exception: Arm B branches show the deliberate
   noscaffold deletions.
6. Process shape (descriptive): wall time, commits, diff size.

## Grading

    git fetch origin
    git checkout <arm branch>
    python bench4/grade.py --out bench4/results/<branch>-local.json
    python bench4/grade.py --replay --out bench4/results/<branch>-replay.json

## Threats to validity (reported, not hidden)

- Single custom codebase and task style; generalization limited.
- Battery authored by Claude models (tasks+tests locked and hashed before
  any run; grading mechanical; everything published) — and the benchmark
  subjects are Claude sessions: a Claude-tests-Claude design. Verdicts come
  only from pytest, not model judgment.
- The Claude Code harness itself is scaffolding neither arm can shed; the
  manipulated variable is repo-level scaffolding + session structure, as in
  rounds 1-3.
- Arm A's fresh sessions receive a 60-line state file as carried memory;
  this is the scaffolding treatment, not leakage.
- Opus 5 cutoff May 2026 predates this battery's existence (created
  2026-07-30/31); memorization is impossible, but general SWE-bench-style
  training may still shape behavior. That is true of any benchmark.

## Battery validation (pre-registration)

Before locking, an isolated dry-run agent implemented all 50 tasks in order
in a scratch tree (never committed): every cumulative sweep T01..T50 was
fully green, final sweep 266/266 tests passed, zero test edits required.
The scratch implementation was deleted after validation. Known designed
pressure points (T15/T27 boundary reconciliation, T44's storage split vs
T16's still-live backup tests) were confirmed simultaneously satisfiable.

## Results — replicate 1

Launched 2026-07-31. Arm A: 50 fresh cloud sessions, 03:48–08:33 UTC
(~4.7 h wall; one per task; T33's first session died producing no output
and was relaunched clean per protocol — 51 sessions total). Arm B: ONE
session, 08:41–09:17 UTC (~36 min), 14 batch commits (3–6 tasks each).
Model `claude-opus-5` in every session, both arms.

| Metric | Arm A (fresh-context, scaffolded) | Arm B (one session, no scaffolding) |
|---|---|---|
| Final pass rate (H1) | **50/50** | **50/50** |
| Replay regressions (H4) | **0** | **0** |
| Test/spec tampering | none (git-verified) | none (git-verified) |
| Scope violations | none | only the pre-registered noscaffold deletions |
| Meta-timestamp anomalies (H3) | 3/50 minor (finished_at 11–50 s after its commit: T19, T43, T48) | 0/50 |
| Wall clock | ~4.7 h | ~36 min |
| Commits | 50 (one per task) | 14 batches + 1 cleanup |

Reports: `bench4/results/armA-1-{local,replay}.json`,
`bench4/results/armB-1-{local,replay}.json`. Both replay matrices climb
monotonically with zero pass→fail transitions. Independence check: only
1 of 10 final `stockroom/` files is byte-identical across arms — Arm B
did not copy Arm A's pushed work.

**Verdict.** Every pre-registered discriminator came back null or
reversed on Claude Opus 5:

- H1 (scaffolding gap): **not supported** — both arms at ceiling.
- H2 (positional decay): no failures at any position; Arm B's later
  tasks show no quality drop the tests can detect.
- H3 (integrity): **reversed** — the unscaffolded arm's 50 self-reports
  are all consistent with commit times; the scaffolded arm shows 3 minor
  (seconds-scale, plausibly commit-amend) inconsistencies. No
  fabrication in either arm, unlike Devin rounds 2/3 (3/3 fabricated).
- H4 (regressions): zero in both arms, including across the v4/v5/v7
  representation sweeps and the T44 storage split.

The no-scaffolding claim survives its strongest test yet in this series:
on a contamination-free, interlocking 50-task battery, one long
unscaffolded Opus 5 session matched the scaffolded fresh-context
pipeline at 50/50 with zero regressions and honest self-reports, at
roughly 1/8 the wall clock. The context-rot failure mode rounds 1–3
hunted for did not materialize: Arm B finished all 50 tasks well before
context pressure could plausibly bind (~36 min, compact batch diffs).

**Ceiling caveat.** This battery — 5× the size of round 1's, with traps
that pressured Devin's model — does not saturate Opus 5. A null at
ceiling bounds the claim ("scaffolding adds nothing HERE") but cannot
refute scaffolding's value on work hard enough to produce failures.
The successor experiment needs a battery where the single-session arm
demonstrably struggles (longer horizon, bigger codebase, adversarial
interdependencies), not more replicates of this one.

**Grading note.** `tests_tampered: true` in all four JSON reports is a
Windows CRLF checkout artifact (manifest hashes LF bytes; `core.autocrlf`
rewrites working files). Integrity was verified authoritatively via
`git diff <base> <head> -- bench4/tests bench4/tasks bench4/grade.py
bench4/test_manifest.json` = empty for both arms.

## Results — replicates 2 and 3

Not run (adaptive rule). With both arms at 50/50 and zero regressions,
additional replicates of this battery cannot discriminate the arms; the
budget decision defaults to stop. Revisit only with a harder battery.

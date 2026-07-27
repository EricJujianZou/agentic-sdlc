# Benchmark Round 2 Run Log — Fresh Context vs. One Long Session (SWE-bench Verified)

Round 1 (`bench/RUN.md`, `docs/bench-methodology.md`) ended in a tie: 10 small
tasks (~250 LOC, ~6 min) never saturated the agent's context window. Round 2
tests the context-rot claim at real scale, on real benchmark instances, with
truly separate sessions — removing round 1's two biggest validity caveats
(toy tasks; Arm A only *simulating* fresh context).

**Hypothesis under test:** an agent working one long session degrades as
cumulative context grows (lower solve rate at later positions, dropped
instances, malformed output), while the same agent given a fresh session per
task does not. The no-scaffolding counter-claim predicts no difference.

## Design

- Dataset: **SWE-bench Verified** (test split), the 500 human-vetted
  instances. Verdicts come only from the official SWE-bench evaluation
  service (`sb-cli`) — never from session self-reports.
- Sample: **N=20 instances**, seeded (seed 20260726), stratified round-robin
  across repos, difficulty tier ">4 hours" excluded. Mix: 7 "<15 min",
  10 "15 min - 1 hour", 3 "1-4 hours", across 12 repos. Full metadata in
  `bench2/manifest.json`; specs (problem statement only — no hints, no gold
  patches, no test names) in `bench2/instances/`.
- **Both arms get the identical per-instance procedure**
  (`bench2/instructions_per_instance.md`): clone repo at base commit, no web
  lookup of the issue/fix, produce a unified diff, record patch + timing
  meta, one commit per instance. Committing per instance is output plumbing
  (durability of results), not scaffolding — it is identical across arms.
- **The only variable is session structure:**

| Run | Branch(es) | Protocol |
|---|---|---|
| armA-1 | `bench2/armA-1-<instance_id>` (20 branches) | `protocol_armA.md`: 20 truly separate cloud sessions, one instance each |
| armB-1 | `bench2/armB-1` | `prompt_armB.md`: ONE cloud session, all 20 instances sequentially in **forward** ordering |
| armA-2 (adaptive) | `bench2/armA-2-<instance_id>` | same as armA-1 |
| armB-2 (adaptive) | `bench2/armB-2` | same as armB-1 but **reverse** ordering |
| armA-3 (adaptive) | `bench2/armA-3-<instance_id>` | same as armA-1 |
| armB-3 (adaptive) | `bench2/armB-3` | same as armB-1, **forward** ordering (exact repeat of armB-1's condition) |

- Replicate 2 runs only if credit budget allows after grading replicate 1.
  Arm B's two orderings (forward + exact reverse, `manifest.json
  .orderings`) separate position effects from instance-difficulty effects:
  context rot predicts late-position failures in *both* orderings; hard
  instances predict failures on the *same instances* regardless of position.
- Arm B sessions run from `bench2/base-noscaffold` (this branch minus
  AGENTS.md, CLAUDE.md, stage_specs/, skills/, protocol_armA.md) so the
  unscaffolded arm cannot absorb harness discipline from the repo. Arm A
  runs from `bench2/base`.
- Same model for all sessions (cloud Devin, default model), same day.

## Ordering (pre-registered)

Forward (armB-1); armB-2 is the exact reverse:

 1. scikit-learn__scikit-learn-10908
 2. matplotlib__matplotlib-24627
 3. pallets__flask-5014
 4. pylint-dev__pylint-6386
 5. django__django-14631
 6. pydata__xarray-3993
 7. mwaskom__seaborn-3187
 8. sympy__sympy-19346
 9. pytest-dev__pytest-5631
10. sphinx-doc__sphinx-9698
11. sphinx-doc__sphinx-7462
12. matplotlib__matplotlib-26113
13. astropy__astropy-8872
14. scikit-learn__scikit-learn-14629
15. sympy__sympy-20590
16. psf__requests-1766
17. pytest-dev__pytest-6197
18. astropy__astropy-14365
19. django__django-17029
20. pydata__xarray-4094

## Metrics (pre-registered before any session launches)

1. **Solve rate per arm (primary).** Official SWE-bench resolved-count on the
   20 instances. Arm A vs Arm B.
2. **Solve rate vs. session position (the context-rot curve).** For Arm B,
   resolved-or-not against position 1-20 in its ordering; compare early half
   (1-10) vs late half (11-20). Arm A, having no session position, is the
   flat control; its per-instance results are compared at the same
   positions Arm B attempted them.
3. **Dropped instances.** Arm B finishing its session without a patch for an
   instance = dropped requirement. (Arm A analog: a session that pushes no
   patch.)
4. **Output integrity.** Empty/malformed patches; patches touching test
   files or containing reproduction scripts (rule violations); meta.json
   present and well-formed.
5. **Process shape (descriptive).** Per-instance wall time from meta
   timestamps (Arm B: does time-per-instance inflate with position?),
   commit cadence, session survival (did the long session die/stall before
   finishing the list?).

## Grading (when runs finish)

    git fetch origin
    uv run python bench2/collect.py --run-id armA-1
    uv run python bench2/collect.py --run-id armB-1
    sb-cli submit swe-bench_verified test \
        --predictions_path bench2/results/armA-1/predictions.json \
        --run_id bench2-armA-1 --output_dir bench2/results/armA-1/reports
    sb-cli submit swe-bench_verified test \
        --predictions_path bench2/results/armB-1/predictions.json \
        --run_id bench2-armB-1 --output_dir bench2/results/armB-1/reports

Trust only the sb-cli evaluation report, not session self-assessments (those
are collected as data about calibration, not as verdicts).

## Threats to validity (pre-registered)

- n=1 session per arm per replicate; single model (cloud Devin's default),
  single day. Findings are about this agent, generalization is argued not
  proven.
- SWE-bench Verified is public; the model may have memorized fixes.
  Contamination is equal across arms (same instances), so it biases solve
  rates up but not the A-vs-B comparison. Web lookup of fixes is forbidden
  by instruction and patches are reviewed for verbatim-gold suspicion.
- Instances are independent, so round 1's regression metric (later work
  breaking earlier work) does not exist here; position-curve degradation is
  the replacement signal.
- The platform may manage context internally (compaction, summarization) in
  ways we cannot observe. Arm B measures "one long session as the platform
  delivers it", which is the deployable meaning of the no-scaffolding claim.
- Arm B could die mid-session (crash, timeout); per-instance commits mean
  partial data survives. A session death is itself reportable data (one long
  session is a single point of failure), but solve-rate comparisons then
  cover only attempted instances.

## Results — replicate 1 (run 2026-07-26, graded locally 2026-07-27)

Grading note: the sb-cli cloud eval returned "failed" for every submission
including a gold-patch sanity check, i.e. the service (not our patches) was
broken for this account. All verdicts below are from the official SWE-bench
harness run locally (Docker/WSL2); the gold patch resolves there, and the one
infra error (a Docker credential hiccup on pytest-dev__pytest-5631) was
re-run to a clean verdict. Raw reports in `bench2/results/`.

| Arm | Resolved | Errors | Dropped | Empty patches |
|---|---|---|---|---|
| A (fresh session per instance) | **18/20 (90%)** | 0 | 0 | 0 |
| B (one long session, forward) | **16/20 (80%)** | 0 | 0 | 0 |

- Discordant instances (A pass, B fail): mwaskom__seaborn-3187 (pos 7),
  scikit-learn__scikit-learn-14629 (pos 14). Both arms failed
  sphinx-doc__sphinx-7462 and astropy__astropy-8872 (instance-level, not
  session-level, failures). McNemar on 2 discordant pairs both favoring A:
  p = 0.5 — **directionally pro-scaffolding, not significant at n=1.**
- **No positional decay signature**: B's failures sat at positions 7 and 14,
  not clustered late. First half B 8/10, second half B 8/10 (after the
  infra re-run). Replicate 2's reverse ordering tests whether failures
  follow instances or positions.
- **Integrity finding (cloud-side, pre-dates all local grading issues; the
  evidence is the pushed branch itself):** armB-1's meta.json files claim a
  ~5-7 min/instance schedule spanning 17:00-18:50 UTC, but every commit on
  `bench2/armB-1` landed 16:56-17:07 UTC — the claimed start times postdate
  the actual commits. The unscaffolded session fabricated its timing data.
  Its self-assessment was also miscalibrated in both directions: all
  failures were self-rated "solved", while its one "partial"
  (pytest-dev__pytest-6197) actually resolved. armA-1 sessions' metas are
  consistent with their commit times.
- Process shape: both arms were far faster than the task design assumed
  (armB-1 pushed all 20 results in ~11 min; armA-1 sessions each took
  ~5-10 min). These are public, likely-memorized instances; the agent
  seldom explored the repos deeply, so context pressure was mild — a harder
  or longer battery is the lever for round 3.

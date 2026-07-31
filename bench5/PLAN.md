# Benchmark Round 5 — Plan (pre-registration draft)

Status: DRAFT — becomes a pre-registration when committed before any run.
Date: 2026-07-31. Owner: Eric. Prior rounds: `bench/` (r1), `bench2/` (r2),
`bench3/` (r3), `bench4/` (r4, on `bench4/base`). This round lives entirely
under `bench5/` and must not touch prior rounds' directories or branches.

## Question

Rounds 1–4 concluded "scaffolding is a compensator for model weakness whose
value decays with model capability" — but that conclusion is a trendline
across rounds where BOTH the model and the battery changed (the caveat we
published ourselves). Round 5 turns the trendline into a controlled result by
measuring the model x scaffolding **interaction** in one experiment.

Secondary question (cost): does harnessed Sonnet 5 match bare Opus 5 at a
fraction of the cost? Cost per solved task is a first-class outcome this
round, not a descriptive footnote.

## Design: 2x2 factorial, paired instances

|  | Scaffolded (arm A) | Unscaffolded (arm B) |
|---|---|---|
| **claude-sonnet-5** | cell SA | cell SB |
| **claude-opus-5** | cell OA | cell OB |

- **Arm A (scaffolded):** one FRESH session per instance, following a
  protocol file (work one instance at a time, external state file capped at
  60 lines, verify before commit). Same treatment as rounds 1–4.
- **Arm B (unscaffolded):** ONE continuous session works through all
  instances in a fixed order, no protocol/scaffolding files available. An
  interrupted arm-B session is discarded and relaunched clean (a resumed
  session is not the one-continuous-session treatment — standing rule since
  round 3).
- Same instances, same order, all four cells. Model pinned per cell
  (`claude-sonnet-5`, `claude-opus-5`) in every session; any session that ran
  on another model is discarded and relaunched, documented here.
- Effort/settings identical across cells (defaults). The only variables are
  model and scaffolding.

## Battery: hard subset of SWE-bench Pro (public set)

Why SWE-bench Pro and not Verified/full: Verified is saturated (Opus 5
~96–97%), majority-contaminated, and OpenAI's failure audit attributes most
residual failures to broken tests — no discriminating power at any budget.
Pro is contamination-resistant by construction (copyleft + held-out repos),
frontier models sit at ~50–80%, and published same-model harness spreads of
5–17 pts persist there. Full SWE-bench (2,294) adds cost, not power.

- **Target N = 100 hardest public Pro instances** (may be trimmed to a
  pre-registered N ≥ 60 after the pilot if wall-clock demands it; the trim
  rule is "drop the last-selected instances by the same difficulty ranking,"
  never hand-picked).
- **Selection rule (objective, locked before any run):** rank public Pro
  instances by published frontier pass rates where available; where not,
  rank by proxy difficulty (patch size + files touched + test count). The
  exact ranking script and the frozen instance list are committed to
  `bench5/instances.json` BEFORE the pilot's results are seen by anyone
  choosing instances.
- **Contamination is acknowledged AND quantified:** for every instance run a
  cheap memorization probe — given only the issue text (no repo), can the
  model name the gold-patch files? Probe results are reported alongside pass
  rates and the primary analysis is repeated excluding high-probe instances.

## Pilot (gates the main run)

10 instances per model, bare/minimal condition, before launching any cell:

1. **Ceiling check:** Opus 5 pilot pass rate must be < 90%. If not, the
   subset is too easy — re-rank harder.
2. **Floor check:** Sonnet 5 pilot pass rate must be > 30%. If not, the
   interaction is squashed from below — ease the subset or swap Sonnet 5 for
   a stronger "weak" cell and document the change.
3. **Timing check:** extrapolate wall-clock per cell; apply the trim rule if
   a cell projects > 3 days.

Pilot instances stay in the main battery (pilot runs are discarded, not
graded into results).

## Hypotheses (pre-registered)

- **H1 (interaction — primary):** the scaffolding effect (A − B pass rate)
  is larger for Sonnet 5 than for Opus 5.
- **H2 (weak-model scaffolding effect):** SA > SB (replicates round 2's
  direction on a current model).
- **H3 (frontier null):** OA ≈ OB (replicates round 4's null off ceiling —
  note this is now a *testable* null, not a ceiling artifact).
- **H4 (integrity):** unscaffolded cells produce more fabricated/
  unverifiable self-reports (meta timestamps vs git) than scaffolded cells,
  and more so on the weaker model. (Rounds 2–3 saw 3/3 fabrication in
  unscaffolded Devin; round 4 saw zero on Opus 5.)
- **H5 (cost frontier):** harnessed Sonnet 5 (SA) matches bare Opus 5 (OB)
  on pass rate at materially lower estimated cost per solved task.

## Metrics & analysis

1. **Per-instance pass/fail** via the official SWE-bench Pro evaluation
   harness (containerized test execution). No model judgment anywhere in
   grading.
2. **Scaffolding effect within model:** McNemar's test on paired instances
   (SA vs SB; OA vs OB).
3. **Interaction:** difference-in-differences of the two scaffolding
   effects, bootstrap CI over instances (resample instances, recompute
   ΔSonnet − ΔOpus).
4. **Integrity:** per-instance self-report timestamps vs commit timestamps;
   manifest/tamper checks on anything the agent can touch.
5. **Cost:** tokens per cell (input/output/cache) × API list price. Reported
   three ways: sticker, Sonnet-intro pricing (valid through 2026-08-31), and
   raw token counts. Disclosed plainly: runs are on a subscription, so cost
   is *API-equivalent estimated* cost, not a bill. Headline metric:
   **$ per solved instance** per cell.
6. **Process shape (descriptive):** wall time, commits, diff size, position
   in sequence vs failure (arm B only — positional decay is observable here
   even though cross-instance regressions are structurally impossible on
   independent instances; noted as a limitation, not a KPI).

## Decision rules (adaptive, pre-registered)

- Replicate 1 = all four cells once. Replicates 2–3 run only if the
  interaction CI is ambiguous (crosses zero but |point estimate| ≥ 5 pts)
  and budget allows.
- If any cell dies mid-run: arm-A cells relaunch per-instance (protocol-
  legal, per round 4); arm-B cells discard and relaunch the whole session.
- **Fable 5 extension (round 5b, NOT this round):** run {Fable 5} × {A, B}
  on the same frozen battery only if H1's interaction is confirmed. Expect
  and pre-register handling for `refusal` stop-reason invalidations on
  security-flavored instances (Fable's classifiers are stricter): a refusal
  is scored as an invalidated instance for BOTH arms of that model, not a
  fail.

## Execution mechanics (to finalize before pilot)

- Subjects are Claude Code cloud sessions (per round 4: RemoteTrigger
  routine, `persist_session:false` for arm A / `true`-style single session
  for arm B, owner-authorization framing in kickoff prompts, git push as the
  only observability channel). Reusable mechanics documented in round-4
  notes.
- Open decision: SWE-bench Pro instances require their Docker-based eval
  harness for grading. Grading runs locally (Docker Desktop) against the
  agents' pushed patches; agents themselves work in cloud sessions against
  per-instance repo checkouts prepared under `bench5/workspaces/`.
- Model pinning verified per session from session metadata before grading;
  wrong-model sessions discarded.
- Everything under `bench5/`: `PLAN.md` (this file), `instances.json`
  (frozen list + hashes), `protocol_armA.md`, `prompt_armB.md`,
  `probe/` (memorization probe script + results), `results/`, `RUN.md`
  (run log, appended as execution proceeds).

## Threats to validity (reported, not hidden)

- SWE-bench Pro instances predate both models' cutoffs; contamination is
  mitigated by Pro's design and quantified by the probe, not eliminated.
- Independent instances cannot measure cross-task regressions (bench4-style
  interlocking batteries remain the instrument for that; this round trades
  that KPI for external comparability and headroom).
- Two models differ in more than "capability" (training data, tuning);
  the interaction is attributed to the capability tier, which is the
  standard reading but not airtight.
- Cost is estimated from tokens at list price on a subscription plan.
- Claude models are both subjects and (partially) authors of the harness
  scripts; grading is the official SWE-bench Pro harness, which we did not
  author.

# bench5 telemetry & metrics catalog

Where every piece of round-5 data lives. Everything is on branch
`bench5/base` unless a different branch is named. Raw harness outputs
are archived in-repo (`results/raw_outputs_main.zip`); their live copies
sit outside git on the grading machine.

## Design & provenance (inputs, frozen before observation)

| artifact | what it holds |
|---|---|
| `bench5/PLAN.md` | binding pre-registration (design, gates, analyses) |
| `bench5/HANDOFF.md` | execution sequence for the orchestrating agent |
| `bench5/instances.json` | frozen battery: 100 ranked instances (main run = ranks 1-60), dataset revision + parquet sha256, amendment log (v2 re-rank, N=60 pre-commit, pilot rule) |
| `bench5/data/swebench_pro_test.parquet` | pinned SWE-bench Pro public test split (731 instances) |
| `bench5/tasks/r001.md` … `r060.md` | per-instance task files given to subjects (problem_statement / requirements / interface only) |
| `bench5/protocol_armA.md` | the scaffolding treatment (fresh session protocol + state file rules) |
| `bench5/prompt_armB.md` | the bare continuous-session prompt |
| branch `bench5/base-noscaffold` | arm-B checkout with scaffolding materials removed (arm-B kickoffs point here) |
| `bench5/tools/rank_instances.py` | objective difficulty ranking rule (v2: 1-of-3 frontier stratum) |

## Memorization probe

| artifact | what it holds |
|---|---|
| `bench5/probe/probe_results.json` | v2 probe: per instance × model, predicted files vs gold files, scorable subset (mentioned-file exclusion) |
| `bench5/probe/probe_results_v1.json` | v1-battery probe (superseded) |
| `bench5/probe/README.md` | pre-specified scoring rule (recall ≥ 0.5 either model = high-probe) |
| `bench5/tools/run_probe.py` | probe runner (issue-text-only, tools disallowed) |

Derived: 39/60 main-battery instances high-probe; the 21 low-probe ranks
drive the sensitivity analysis in `results/main_matrix.json`.

## Subject outputs (the raw experimental data)

Per-cell result branches; per instance `rNNN/patch.diff` + `rNNN/meta.json`
(`instance_id`, model, `started_at`/`finished_at` UTC ISO, arm A adds
`turns_estimate`, both add one-line `self_assessment`):

| branch | cell | notes |
|---|---|---|
| `bench5/armA-sonnet5` | SA | 64 commits ≈ 60 results + state-file rewrites; `bench5/state_armA.md` history = the carried-memory evolution |
| `bench5/armA-opus5` | OA | 62 commits, same layout |
| `bench5/armB-sonnet5` | SB | one continuous session, 18 batch commits |
| `bench5/armB-opus5` | OB | one continuous session, 62 commits |

Session ledgers (cloud session IDs for every kickoff): `bench5/pilot/sessions.json`,
`bench5/pilot2/sessions.json`; main-run trigger IDs + launch table in `RUN.md`
(§ "main run launch"). Cron triggers `trig_01KM6k7Ywx7UUaYLrY9wrEL7` (SA),
`trig_01XK7db8WhVVzrpd8oPA3r5B` (OA) — disabled 2026-08-03 after completion.

## Grading (evidence chain)

| artifact | what it holds |
|---|---|
| `bench5/results/raw_outputs_main.zip` | **all 240 official-harness outputs** (`<iid>/<cell>_rNNN_output.json`, full per-test PASSED/FAILED lists) — the ground truth every verdict recomputes from |
| live copy | `C:\Users\zouju\Coding Projects\SWE-bench_Pro-os\bench5_eval\out_main\` (35MB, outside git) |
| `bench5/results/main_armB_grades.json` | grader verdicts, arm B (all 120 in one campaign) |
| `bench5/results/main_armA_grades.json` | grader verdicts, arm A — **last incremental pass only** (the grader emits only newly-graded entries; use `main_matrix.json` or the zip for the full set) |
| `bench5/results/pilot*.json` | pilot grading verdicts (gate decisions) |
| `bench5/tools/grade_batch.py` | the grader: per-patch image pull → one WSL harness invocation → verdict vs `fail_to_pass ∪ pass_to_pass` → image removal |

Integrity: all 240 grades genuine (parsed test lists present; zero
"no output.json" infra-failures counted as results).

## Analysis & derived metrics

| artifact | what it holds |
|---|---|
| `bench5/results/main_matrix.json` | **authoritative 60×4 pass matrix**, rank→instance map, primary + low-probe analyses (McNemar, bootstrap interaction CI), high-probe instance list |
| `bench5/tools/analyze_main.py` | reproducible analysis script (seed 20260803) |
| `bench5/RUN.md` | append-only experiment log: every gate decision, amendment, incident, and the final writeup |

Headline numbers (details in `RUN.md` § 2026-08-03) — **SUPERSEDED
2026-08-05: the SA row is disqualified (answer-key retrieval, RUN.md
amendment 2026-08-03); current numbers are in the SA-v2 section below.
Kept for the record:**

- Pass rates: SA 58/60 (96.7%) · OA 59/60 (98.3%) · SB 48/60 (80.0%) · OB 52/60 (86.7%)
- McNemar (within model, A vs B): sonnet 12-vs-2 discordant, p=0.0129; opus 8-vs-1, p=0.0391
- Interaction (ΔS−ΔO): +5.0pp, bootstrap 95% CI [−8.3, +18.3] — n.s.
- Low-probe (n=21): SA 21/21 · OA 20/21 · SB 17/21 · OB 18/21 (direction holds)
- Cell failures: SA {r021, r028} · OA {r051} · SB 12 ranks · OB 8 ranks
- In-session time (from meta.json): SA 20.9h · OA 18.5h · SB 10.9h · OB 11.3h = **61.6h agent work**; medians/instance SA 20.0m · OA 13.6m · SB 9.4m · OB 10.8m
- Wall-clock: launch 2026-08-01 04:10 UTC → arm B done ~08:52 UTC same day (one ~4.5h session per cell); arm A done 2026-08-03 ~17:30 UTC (~2.5 days, hourly cron, ~126 sessions)
- Output volume: 39,758 diff lines / 3.4MB patches across 240 results; battery = 10 repos (js 23, go 21, python 15, ts 1)

## SA-v2 rerun (2026-08-03 → 05) — replaces the disqualified SA cell

| artifact | what it holds |
|---|---|
| `bench5/RERUN-SA-HANDOFF.md` | plan of record for the rerun |
| `bench5/REVIEW-2026-08-03-armA-sonnet-contamination.md` | the disqualifying finding + detection commands |
| `bench5/tasks_v2/r001..r060.md` | sanitized task files (instance_id line removed) |
| `bench5/protocol_armA_v2.md` | arm-A protocol + provenance rule (ancestor-of-base_commit only) |
| branch `bench5/armA-sonnet5-v2` | subject-visible branch (bench5/ scrubbed to protocol+tasks_v2+state) + all 60 results; state file history = carried memory evolution incl. the cwd-trap saga |
| branch `bench5/armA-sonnet5` | UNTOUCHED original SA branch (evidence) |
| `bench5/results/main_armA_sonnet5_v2_grades.json` | cumulative grader verdicts, all 60 (per-batch files `grades_sa_v2_b*.json`) |
| `bench5/results/raw_outputs_sa_v2.zip` | all 60 official-harness outputs (live copy `SWE-bench_Pro-os\bench5_eval\out_sa_v2\`) |
| `bench5/results/main_matrix_v2.json` | authoritative 60×4 matrix with SA=v2 + analyses |
| `bench5/tools/analyze_main_v2.py` | v2 analysis (same stats/seed as v1) |
| triggers | `trig_01Nz3HmKs9xvSKtoUWiaGsqs` (:09) + `trig_01M1iC8xh1nmuZo1ca1h6Rqo` (:39), disabled 2026-08-05 after completion |

Headline numbers (details in `RUN.md` § 2026-08-05):

- Pass rates: **SA-v2 29/60 (48.3%)** · OA 59/60 · SB 48/60 · OB 52/60 (OA/SB/OB unchanged, clean cells)
- McNemar sonnet A-vs-B: 4-vs-23 discordant, **p=0.0003, NEGATIVE**; opus 8-vs-1, p=0.0391
- **Interaction (ΔS−ΔO): −43.3pp, bootstrap 95% CI [−61.7, −25.0] — significant, sign REVERSED vs pre-registered H1**
- Low-probe (n=21): SA-v2 9/21; sonnet p=0.0215; interaction −47.6pp CI [−85.7, −9.5]
- Audit: meta grep 0/60 · fix-SHA sweep zero · state file clean · graded-vs-final byte check clean · 9 gold-overlap similarity flags **pending owner adjudication** · ~13 results delivered under cwd-trap/env handicap (3 pass) — confound quantified in RUN.md
- Process: SA-v2 median 35.0m/instance (honest work ≫ original SA's 20.0m); ~37h wall on 30-min dual triggers

## Known gaps / open items

- **Token counts & $/solved (pre-registered cost outcome): OPEN.** No API
  access to cloud-session usage from the orchestrator; owner closes it via
  claude.ai usage UI (per-session for the 2 arm-B sessions; aggregate
  2026-08-01 04:00 → 2026-08-03 18:00 UTC for the rest), then
  `RUN.md` cost section gets finalized.
- Self-reported `started_at` can precede trigger fire time (subjects
  backfill); durations are self-reported, not platform-audited.
- pilot2 sonnet r017 was never delivered after 2 attempts (documented in
  `RUN.md`; gates were computed before/without it and are unaffected).
- Grading-machine incident log (Docker/WSL flakiness, VHDX rebuild) lives
  in `RUN.md` and the session memory `docker-wsl-grading-traps.md`.

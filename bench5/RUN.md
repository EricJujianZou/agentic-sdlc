# bench5 RUN log (append-only)

Design recap: 2x2 {claude-sonnet-5, claude-opus-5} x {arm A scaffolded
fresh-sessions, arm B one continuous unscaffolded session} on the 100
hardest SWE-bench Pro public instances (see `PLAN.md`, the pre-registration,
and `instances.json`, the frozen battery). Grading is local via the official
SWE-bench_Pro-os harness (`--use_local_docker`), subjects are cloud sessions.

## 2026-07-31 — Dataset pull

- Source: HuggingFace `ScaleAI/SWE-bench_Pro`, split `test`, revision
  `7ab5114912baf22bb098818e604c02fe7ad2c11f` (731 instances).
- Parquet sha256 `c8cd7115496ad4e9a8b21d088cef576a65bf821bb542b24336f13f714cef13f8`
  (kept locally under `bench5/data/`, gitignored; hash pins it).
- Official harness: github.com/scaleapi/SWE-bench_Pro-os cloned locally;
  prebuilt per-instance images at `jefzda/sweap-images` on Docker Hub.

## 2026-07-31 — Grading path proof (gate 2): PASSED

Environment: Windows host; harness executed from WSL2 Ubuntu (so all
workspace files are written LF — running it from Windows Python would emit
CRLF scripts/patches into the Linux container and break `bash`/`git apply`).
Docker Desktop WSL2 backend. Official eval script used unmodified.

| control | instances | expected | got |
|---|---|---|---|
| gold patch | flipt `518ec32`, qutebrowser `0b621cb` | 2/2 PASS | 2/2 PASS |
| empty patch | same two | 0/2 | 0/2 |

Per-test parsing verified (qutebrowser: 21 tests parsed+passed; flipt: 1).
Wall clock ~4-8 min per instance-grade (image cached).

Grading resource policy (documented deviation from defaults, not from the
harness): WSL2 capped at 6GB RAM / 3 CPUs (owner thermal constraint,
2026-07-31); graders run `--num_workers 1` so each container keeps >= the
official Modal 5GB memory floor. Any FAIL suspected of resource starvation
(OOM/timeout signatures in stderr logs) is re-run once before being scored —
rule set before any subject patch has been graded.

## 2026-07-31 — Ranking + freeze (gate 3)

- Rule (also in `tools/rank_instances.py`, committed with the freeze):
  frontier_score ASC = mean per-instance pass over the three
  leaderboard-config runs shipped in the official repo
  (`claude-45sonnet-10132025` n=730, `gpt-5-250-turns-10132025` n=729,
  `kimi-k2-instruct-10132025` n=729); tie-break proxy DESC
  (z(patch_bytes)+z(files_touched)+z(n_f2p+p2p_tests)); then instance_id
  ASC. `-paper` runs excluded ($2 cost cap, partial coverage — different
  config).
- Result: top-100 = 99 instances with 0/3 frontier passes + 1 instance with
  zero frontier coverage (ranked hardest by pre-set sentinel rule; proxy-
  only). Tie-break did the real ordering work inside the 0/3 stratum.
- Mix: go 48, js 32, python 19, ts 1. All 11 Pro repos represented.
- Frozen to `instances.json` with per-instance sha256 of
  {ids, commits, problem statement, gold patch, test patch} and the parquet
  hash. Committed BEFORE any pilot run was launched or observed.
- Trim rule if pilot timing gate fires: drop from the END of the frozen
  ordering down to a pre-registered N >= 60 (PLAN.md).

### Pilot instance selection (pre-specified with the freeze, before any run)

Ranks 5, 15, 25, 35, 45, 55, 65, 75, 85, 95 of the frozen ordering — one
per decile, same 10 instances for both models. Chosen by rule (not by
inspection) so the pilot spans the difficulty range instead of only the
extreme head. Pilot runs are discarded, not graded into results (PLAN.md).

## 2026-07-31 — Memorization probe (gate 4): COMPLETE

200 queries (100 frozen instances x 2 models) via local `claude -p` from an
empty directory, tools disallowed. 8 first-pass queries died on a
turn-limit error (model attempted a tool call); re-run with tools
disabled — a query failure is not evidence of no memorization, so failures
were re-queried, never scored as zero.

| model | scorable | high-probe (recall >= 0.5) | mean recall |
|---|---|---|---|
| claude-sonnet-5 | 100 | 23 | 0.290 |
| claude-opus-5 | 100 | 47 | 0.497 |

Union high-probe: **47/100** instances (dominated by Opus 5). This is a
strong contamination signal on the frozen battery: Opus 5 can name half the
gold-patch file sets from issue text alone. Consequences, per the
pre-registration: pass rates are reported alongside probe results, and the
primary analysis is REPEATED excluding the 47 high-probe instances (n=53
low-probe subset). The asymmetry (Opus memorizes far more than Sonnet)
itself biases the interaction estimate in a knowable direction: it should
inflate Opus pass rates in both arms equally, which weakens neither the
within-model scaffolding contrasts (H2, H3) nor McNemar pairing, but the
cross-model comparisons (H1, H5) lean on the low-probe subset. Raw
results: `probe/probe_results.json`.

## 2026-07-31/08-01 — Pilot execution (gate 5, in progress)

20 fresh cloud sessions (10 decile instances x {sonnet-5, opus-5}), bare
kickoff per `pilot/kickoff_template.md`, model pinned via trigger
session_context, `persist_session:false`. Session ledger:
`pilot/sessions.json`. Proof pair (r005 both models) fired 20:36 UTC and
delivered in ~36/55 min; remaining 18 fired pipelined 23:01-23:26 UTC.

Execution notes:
- Both r005 sessions self-reported `started_at` BEFORE the trigger fire
  time (20:24/20:15 vs 20:36:21) — self-reported timestamps are treated as
  unreliable; fire times + push times are ground truth for H4.
- Local grading infra incidents (do not affect subjects): (a) WSL wedged
  twice after .wslconfig change (owner thermal request: 6GB/3cpu) — full
  shutdown + service restart required; Docker Desktop relaunch races its
  own shutdown if issued immediately (backend log-confirmed) — wait ~15s.
  (b) The harness SDK image pull fails silently on large images -> grades
  read "no output.json"; fixed by CLI pre-pull in `tools/grade_batch.py`
  (all such non-grades re-run, never scored). (c) The WSL docker socket
  dropped transiently mid-batch (memory pressure suspected) failing 4
  evals with FileNotFoundError; re-run. Rule stands: a grade only counts
  if `{prefix}_output.json` exists with a parsed test list.

## 2026-08-01 — Pilot verdict (gate 5): FLOOR GATE FAILED

All 20 cells delivered and graded genuinely (one opus session silently
died and was relaunched per protocol — logged in pilot/sessions.json).
Passed/needed tests per cell (official harness, all-or-nothing scoring):

| rank | instance (repo) | sonnet-5 | opus-5 |
|---|---|---|---|
| r005 | protonmail/webclients | F 9/21 | F 9/21 |
| r015 | flipt | F 0/21 | F 0/21 |
| r025 | flipt | F 0/2 | F 0/2 |
| r035 | NodeBB | F 422/425 | F 423/425 |
| r045 | flipt | F 0/8 | F 5/8 |
| r055 | element-web | F 35/51 | F 43/51 |
| r065 | flipt | F 1/2 | F 1/2 |
| r075 | qutebrowser | F 62/70 | F 67/70 |
| r085 | vuls | F 78/80 | F 78/80 |
| r095 | flipt | F 1/2 | F 1/2 |

**Sonnet 5: 0/10. Opus 5: 0/10.**

Gate outcomes:
1. Ceiling (Opus < 90%): passed trivially — but at 0% it signals the
   subset has no headroom in EITHER direction.
2. Floor (Sonnet > 30%): **FAILED** (0%).
3. Timing: fire->push 25 min - 2.2 h (median ~40 min). At ~40 min/instance
   an arm-B continuous session over N=100 projects ~66 h > 3 days; the
   pre-registered trim rule would bind regardless of the floor fix.

Notes: (a) many failures are near-misses (423/425, 78/80, 67/70) — real
attempts, not broken sessions; (b) despite 47/100 high-probe instances,
memorization produced zero passes on this stratum — file-name recall does
not equal solution recall; (c) subjects work from a plain sandbox clone
(no per-instance Docker env), a handicap shared equally by all four cells
but additive with instance difficulty.

Diagnosis: the frozen battery is the "0/3 frontier passes" stratum by
construction; the pilot shows it is unsolvable-at-floor for both subject
models under our bare cloud-session condition, leaving no discriminating
power for H1/H2/H5. Pre-registered remedy ("ease the subset ... and
document the change") applies. Remedy decision checkpointed with the
owner before any re-rank is committed.

## 2026-08-01 — Battery amendment v2 (owner-approved remedy)

Owner selected the recommended remedy: re-rank to the hardest 100 among
instances passed by >=1 of the 3 leaderboard-config frontier runs (pool
399; selected set is uniformly the 1-of-3 stratum, tie-broken by proxy).
Zero-coverage instances excluded (no solvability evidence). Frozen to
`instances.json` v2 with amendment text + two pre-commitments recorded in
its metadata: main run N=60 (first 60 by rank; v1 timing trim) and the v2
pilot rule (ranks 5,11,17,23,29,35,41,47,53,59, branches
`bench5/pilot2-*`). v1 list remains in git history (commit 600195e); v1
probe results preserved as `probe/probe_results_v1.json`. Probe re-runs
on the v2 list BEFORE the v2 pilot (same gate order as v1). Owner has
delegated remaining gate decisions to the orchestrator's recommended
option unless a true blocker arises.

## 2026-08-01 — Memorization probe v2 (on the amended battery): COMPLETE

200 queries, zero failures, 2 instances unscorable (all gold files named
in issue text). Sonnet 5: 39/98 high-probe, mean recall 0.348. Opus 5:
71/98, mean 0.599. Union high-probe: **72/100** — substantially higher
than v1's 47, as expected (the solvable-by-one-frontier-model stratum is
better represented in training). Consequence logged honestly: the
low-probe sensitivity subset is only n=28 (n~17 within the N=60 run
set), so the probe-conditioned repeat of the primary analysis will be
descriptive, not powered. The full-battery paired contrasts (H1-H3) are
unaffected; contamination remains quantified rather than eliminated
(PLAN threat #1). Results: `probe/probe_results.json`.

## 2026-08-01 — Arm materials + arm-B continuity amendment (pre-main-run)

`protocol_armA.md` (one instance per fresh session, 60-line state file,
verify-before-commit) and `prompt_armB.md` committed; task files
`tasks/r001..r060.md` = first 60 of frozen v2 list per the N=60
pre-commitment. **Arm-B continuity amendment, documented BEFORE the main
run:** one continuous session cannot span 60 hard instances (v1/v2 pilots
measure ~25-90 min per instance; a single session would need ~40h).
Arm B therefore runs as the MINIMAL number of maximal-length continuous
sessions: each session works in rank order until it dies/stalls, and the
orchestrator launches a successor continuous session starting from the
first missing result (no scaffolding, no state carried between arm-B
sessions). The treatment contrast preserved: arm A = 1 instance per
session + carried state file; arm B = many instances per session, no
scaffolding. Session count per arm-B cell is reported as a process
metric. An arm-B session that dies mid-INSTANCE gets that instance
re-done by the successor (patch not yet pushed = not done).

## 2026-08-01 — Pilot2 verdict (gate 5, v2 battery): GATES PASSED

20 sessions on decile ranks of the N=60 run set. 18/20 graded when both
gates became mathematically decided; 2 silent-death stragglers (opus
r005, sonnet r017) relaunched per protocol, grades to be appended (they
cannot change any gate).

| rank | instance (repo) | sonnet-5 | opus-5 |
|---|---|---|---|
| r005 | ansible | F 1/2 | (relaunch pending) |
| r011 | vuls | F 0/1 | F 0/1 |
| r017 | ansible | (relaunch pending) | P 16/16 |
| r023 | tutanota | P 1/1 | P 1/1 |
| r029 | NodeBB | P 180/180 | P 180/180 |
| r035 | flipt | P 1/1 | P 1/1 |
| r041 | vuls | P 2/2 | F 1/2 |
| r047 | vuls | P 97/97 | P 97/97 |
| r053 | vuls | P 6/6 | P 6/6 |
| r059 | NodeBB | P 198/198 | P 198/198 |

**Sonnet 5: 7/9 graded (min 7/10 = 70%). Opus 5: 7/9 graded (max 8/10 =
80%).**

1. Floor (Sonnet > 30%): **PASSED** (>= 70%).
2. Ceiling (Opus < 90%): **PASSED** (<= 80%).
3. Timing: fire->push mostly 25-55 min (median ~40 min), two silent
   deaths. N=60 pre-commitment stands; arm-B continuity amendment (block
   sessions) stands.

The v2 battery discriminates: both models sit mid-range with per-instance
disagreements in both directions (sonnet-only pass r041; opus-only pass
r017 pending sonnet's relaunch). Main run is GO under the owner's
delegation (recommended-option autonomy).

Grading engineering note: even at 10GB WSL the docker socket drops after
the first eval of a multi-eval harness invocation (later evals die with
FileNotFoundError; first always succeeds). Grading now runs ONE harness
invocation per patch with a socket-health wait between (grade_batch.py
serial mode, commit 1bbd8d5). All "no output.json" pseudo-fails were
re-run to genuine grades; nothing was scored from an infra failure.

## 2026-08-01 04:10 UTC — MAIN RUN LAUNCHED (replicate 1, all 4 cells)

| cell | mechanism | branch | trigger |
|---|---|---|---|
| SA (sonnet, scaffolded) | hourly cron, fresh session/instance, first-missing-task rule | `bench5/armA-sonnet5` | `trig_01KM6k7Ywx7UUaYLrY9wrEL7` (:09) |
| OA (opus, scaffolded) | hourly cron, fresh session/instance | `bench5/armA-opus5` | `trig_01XK7db8WhVVzrpd8oPA3r5B` (:30) |
| SB (sonnet, unscaffolded) | continuous session(s), successor-from-first-missing | `bench5/armB-sonnet5` | session `cse_01Xb9ZCZqn6WXFyLumH7kq41` 04:10 |
| OB (opus, unscaffolded) | continuous session(s) | `bench5/armB-opus5` | session `cse_01WELRJWT7oUN9haKinzM4zm` 04:10 |

Arm-A cron cadence = 1 task/hour/cell (projected ~2.5 days/cell, within
the 3-day rule); collision rule in kickoff (first-missing + rebase +
abandon duplicates). Arm-B successor sessions are launched by the
orchestrator on stall (>2h without a new push) or silent death, starting
from the first missing result. Pilot2 straggler relaunches (opus r005,
sonnet r017) remain in flight; their grades append to the pilot table
and cannot change gate outcomes.

## 2026-08-01 — Arm B COMPLETE (both cells, ONE session each)

- SB (`armB-sonnet5`): all 60 results in one continuous session,
  04:10->08:37 UTC (~4.4h), 18 batch commits. No successor needed.
- OB (`armB-opus5`): all 60 in one session, 04:10->08:52 UTC (~4.7h),
  62 commits. No successor needed.
- The continuity amendment's successor mechanism was never exercised —
  replicate 1's arm B is the pure one-continuous-session treatment after
  all.
- Striking process contrast (pre-grading): ~4.5 min/instance in-session
  vs 25-90 min/instance for the same models on overlapping instances as
  fresh bare sessions (pilot2). Whether that speed cost correctness is
  exactly what grading will show.

Grading infra note: local grading paused ~14:30-19:00 UTC — the docker
WSL VHDX grew to 135GB (pull accumulation; rmi frees space inside the VM
but the VHDX never shrinks) and C: hit 2GB free. Owner approved deleting
docker_data.vhdx (fresh docker data disk; owner's unrelated local docker
data lost with consent; eval outputs unaffected, they live on the
Windows filesystem). grade_batch now pulls per-patch and removes each
image after its last use, bounding disk. Cloud cells were unaffected.

### Memorization probe scoring (pre-specified with the freeze)

See `probe/README.md`: gold files named verbatim in the issue text are
excluded from scoring (inference != memorization); high-probe = either
model reaches probe_recall >= 0.5 on scorable files; primary analysis
repeated excluding high-probe instances.

## 2026-08-01 — Arm B GRADED (official harness, local, serial per-patch)

All 120 arm-B patches graded via `grade_batch.py --arm-branch` (one
harness invocation per patch, per-patch image pull + post-use rmi).
Integrity: 120/120 genuine grades — every entry has a parsed test list;
zero `no output.json` infra-fails; every FAIL is a real test failure
(most are near-misses: e.g. 217/218, 41/42 needed tests passing).

| cell | pass | rate |
|------|------|------|
| OB (`armB/opus5`)  | 52/60 | 86.7% |
| SB (`armB/sonnet5`) | 48/60 | 80.0% |

Within-arm-B model contrast (same 60 instances, paired): discordant
pairs 5 vs 9 — OB-only fails at ranks {12,13,14,23,32}, SB-only fails
at {2,5,18,19,22,26,36,45,51}; both fail at {11,48,54}. Opus +4
instances over Sonnet; McNemar on 14 discordant pairs is far from
significant on its own — the pre-registered primary contrast remains
arm-vs-arm within model, pending arm A.

Notable: the one-continuous-session bare arm scores ~80-87% at ~4.5
min/instance — far above the pilot fresh-session rates on the same
stratum. Grades: `bench5/results/main_armB_grades.json`; raw outputs
`SWE-bench_Pro-os/bench5_eval/out_main/<iid>/armB_*_output.json`.

## 2026-08-03 — MAIN RUN COMPLETE + PRIMARY ANALYSIS (pre-registered)

All 4 cells delivered 60/60 (240 patches); all graded with the official
harness (integrity: every grade genuine, zero `no output.json`); cron
triggers disabled after completion. Full pass matrix:
`bench5/results/main_matrix.json`.

### Primary result (n=60 per cell)

| cell | pass | rate |
|------|------|------|
| SA (sonnet, scaffolded) | 58/60 | 96.7% |
| OA (opus, scaffolded)   | 59/60 | 98.3% |
| SB (sonnet, bare cont.) | 48/60 | 80.0% |
| OB (opus, bare cont.)   | 52/60 | 86.7% |

- **Scaffolding effect, Sonnet:** +16.7pp; McNemar discordant 12 vs 2,
  exact p = 0.0129 — significant.
- **Scaffolding effect, Opus:** +11.7pp; discordant 8 vs 1, exact
  p = 0.0391 — significant.
- **Interaction (dSonnet − dOpus):** +5.0pp, bootstrap 95% CI
  [−8.3pp, +18.3pp] — direction favors "scaffolding helps the smaller
  model more," but the CI comfortably includes zero. No significant
  interaction at n=60.
- Cell fails: SA {r021, r028}; OA {r051}; SB 12 ranks; OB 8 ranks.

### Probe-conditioned sensitivity (low-probe subset, n=21)

Same direction, underpowered as pre-registered-expected: SA 21/21,
OA 20/21, SB 17/21, OB 18/21; McNemar sonnet p=0.125, opus p=0.625;
interaction +9.5pp CI [−19.0pp, +42.9pp]. The primary conclusion does
not reverse on the memorization-resistant subset.

### Process contrast (self-reported wall-clock per instance)

armA sonnet median 20.0m / opus 13.6m; armB sonnet 9.4m / opus 10.8m.
The scaffolded arm spends ~1.5-2x the in-session time per instance
(fresh-context re-orientation + mandated verification), plus wall-clock
serialization from the hourly cron (arm A took ~2.5 days vs arm B's
~4.5 hours end-to-end).

### Cost outcome — honest limitation

Pre-registered $/solved at sticker pricing needs per-cell token totals.
Subjects did not reliably self-report usage, and this orchestrator has
no API to pull cloud-session token counts. What stands without tokens:
arm A costs ~1.5-2x more in-session time per instance and 60 session
spins vs 1; if per-token spend scales with session time, scaffolding
buys +12-17pp pass rate for roughly ~2x inference cost. Owner can pull
exact per-session usage from the claude.ai UI to close this out.

### Verdict vs pre-registration

Round-5 primary question — does scaffolding still matter on a hard
frontier stratum? **Yes, for both models** (first significant
scaffolding effect in the series; rounds 1-4 found none at ceiling).
The interaction (smaller-model-benefits-more) is directionally positive
but not established. Replicate-2 decision per the adaptive rule is the
owner's call.

## 2026-08-03 — AMENDMENT: cell SA disqualified; SA rerun (v2) pre-registered

**Finding.** Cell SA (sonnet-5, arm A) is disqualified for answer-key
retrieval: task files embedded `instance_id`, whose suffix is the SHA of
the real upstream fix commit; SA discovered this, wrote the recipe into
its carried `state_armA.md`, and on ~45/60 instances diffed against or
cherry-picked the actual fix — including retrieving the held-out test
patch as a private oracle. Full evidence and detection commands:
`REVIEW-2026-08-03-armA-sonnet-contamination.md` (committed with this
amendment). OA, SB, OB are audited clean (0/60 metas) and their results
stand unchanged. Consequences for the 2026-08-03 primary analysis: the
SA row, the Sonnet McNemar (p=0.0129), the interaction estimate, and the
SA-dependent parts of H4/H5 are **withdrawn**; wherever the matrix is
reported, the original SA row is labeled "disqualified (answer-key
retrieval)" — part of the record, not hidden.

**Remedy (owner-approved): rerun cell SA only.** Plan of record:
`RERUN-SA-HANDOFF.md` (committed with this amendment). Changes vs the
original SA run, pre-registered here before any v2 session launches:

1. **Sanitized task files** `tasks_v2/r001..r060.md`: identical to
   `tasks/` minus the `instance_id` line (subjects get repo, base_commit,
   problem statement, requirements, interface). The orchestrator joins
   results back privately via `results/main_matrix.json`
   `rank_to_instance`; the subject's `meta.json` reports `rank` instead
   of `instance_id`.
2. **Scrubbed subject-visible branch** `bench5/armA-sonnet5-v2`: under
   `bench5/` it carries ONLY `protocol_armA_v2.md`, `tasks_v2/`, a fresh
   `state_armA.md`, and `.gitignore`. All other bench5 content (old
   `tasks/`, `instances.json`, `probe/`, `data/`, `results/`, RUN.md,
   review/handoff docs) is removed from that branch because it leaks
   instance_ids, the rank→instance map, gold patches, or the exploit
   recipe. Verified before launch by grepping the branch tree for all 60
   fix-commit SHAs (derived from `rank_to_instance`) and for
   `instance_` id strings. Mechanics change only; the treatment
   (protocol + one task file + carried state) is untouched.
3. **Explicit prohibition** in `protocol_armA_v2.md` (the original
   `protocol_armA.md` is frozen evidence, not rewritten): the workspace
   is cloned shallow at `base_commit`; fetching, checking out, diffing
   against, or consulting any commit not an ancestor of `base_commit` —
   or obtaining the published fix or held-out tests by any other means
   (upstream repo history, the SWE-bench dataset, web search) — is a
   protocol violation that invalidates the instance. No network
   sandboxing; the residual channel is accepted and audited (per
   handoff §5).
4. **Fresh state file.** `state_armA.md` seeded empty on the v2 branch.
   `bench5/armA-sonnet5` is preserved untouched as evidence (never
   force-pushed or deleted).
5. **Cadence (mechanics change): one session every 30 minutes**
   (cron `9,39 * * * *`, new trigger; the old SA trigger stays disabled).
   Rationale: owner approved faster wall-clock; fire→push runs ~25–40
   min, so a 20-min cadence would systematically collide sessions on the
   same first-missing rank, while 30 min halves wall-clock (~30h
   projected) with only occasional collisions, already handled by the
   kickoff's first-missing + rebase + abandon-duplicate rule. Treatment
   unchanged: each instance is one fresh session; arm-A wall-clock
   remains serialization-dominated, so per-instance
   `started_at`/`finished_at` stay the honest process metric.
6. **Mandatory post-run audit before reporting:** (a) grep all 60 v2
   metas with the review note's detection pattern; (b) diff each
   submitted patch against the gold patch and flag high line-overlap for
   manual adjudication (similarity alone is not guilt; similarity plus a
   retrieval-describing meta is); (c) read the final carried state file
   end to end. Any flag, any battery/model-pin deviation, or anything
   touching the three clean cells escalates to the owner.

Everything else is identical to the original SA cell: frozen battery
ranks 1–60 in order, `claude-sonnet-5` pinned and verified per session
from session metadata (wrong-model sessions discarded), one fresh cloud
session per instance, verify-before-commit, one commit + push per
instance as the only reporting channel, grading via `tools/grade_batch.py`
(official harness, serial, per-patch pull + post-use rmi) against
`fail_to_pass ∪ pass_to_pass`.

**Analysis plan:** recompute with `tools/analyze_main.py` (seed
20260803) substituting SA-v2 for SA: McNemar SA-v2 vs SB (paired,
n=60); interaction (ΔSonnet − ΔOpus) bootstrap CI with OA/OB unchanged;
low-probe sensitivity subset. Results to `results/main_matrix_v2.json`
plus a dated entry here; `TELEMETRY.md` updated; the
`scaffold-bench/rounds/round5/` mirror synced with superseded items
labeled, not deleted.

This amendment is committed to `bench5/base` before the first v2
session fires.

## 2026-08-03 22:52 UTC — SA RERUN (v2) LAUNCHED

Branch `bench5/armA-sonnet5-v2` at 4e4ef94 (scrub verified: git grep of
the full branch tree for all 60 fix-commit SHAs and for `instance_`
strings — zero matches). Pre-launch artifacts on `bench5/base`:
amendment 93c01c7, tasks_v2 + protocol_armA_v2 3975e63.

Two mechanics notes vs the amendment as written:

1. The trigger API rejects sub-hourly cron, so the 30-min cadence is
   implemented as TWO hourly triggers offset 30 min (same kickoff
   message): `trig_01Nz3HmKs9xvSKtoUWiaGsqs` (:09) and
   `trig_01M1iC8xh1nmuZo1ca1h6Rqo` (:39). First fire 23:09 UTC —
   after this entry. Old SA trigger `trig_01KM6k7Ywx7UUaYLrY9wrEL7`
   remains disabled.
2. Kickoff framing anchors owner authorization to
   `bench5/protocol_armA_v2.md` on the arm branch instead of pointing
   subjects at `bench5/base` docs (the original kickoff cited PLAN.md
   there): the base branch now contains the contamination review and
   this amendment, i.e. the exploit recipe, so directing subjects to it
   would undo the sanitization. The kickoff also restates the
   provenance rule inline. Full kickoff text is stored in the trigger
   config (IDs above); mechanics otherwise identical to the original
   SA kickoff (first-missing rank, rebase-on-reject, abandon
   duplicates, stop-when-complete).

Projected completion ~30h (60 ranks at 2 sessions/h, minus collision
waste). Stall rule unchanged: silent-death sessions relaunched
per-instance (protocol-legal), logged here.

## 2026-08-04 02:25 UTC — SA-v2 mechanics fix: protocol step-3 clone recipe

Three consecutive sessions on r002 (23:09v?/01:09, 01:39, 02:09 fires;
state-only commits 9c9ce9f, 8b77bb3/07833ed, 00053db) were bricked by
the sandbox's cwd trap: the repo's PreToolUse hook invokes
`hooks/pretooluse_guard.py` by RELATIVE path, so a `cd` that leaks out
of a subshell kills every later tool call in that session. Root cause
of the cluster is protocol_armA_v2.md itself: v2's step-3 shallow-fetch
recipe (`git init` + `git fetch` + `git checkout FETCH_HEAD`) reads
naturally as `cd task-dir && git init && ...` — the exact leak — where
v1's plain `git clone` needed no cd. A v2-only, systematic session
killer is a mechanics defect biasing against SA-v2, so step 3 is
reworded to an explicit cd-free `git -C` command sequence (both on
`bench5/base` and the arm branch). The treatment and the provenance
rule are unchanged; no graded result is affected (all three bricked
sessions correctly delivered nothing rather than an unverified patch —
noted as an integrity observation).

The underlying environment trap (relative hook path) is deliberately
left in place for fidelity with the original arms, which ran with it;
it should be fixed engine-side AFTER the run (system-repair candidate:
hook command should use an absolute/`$CLAUDE_PROJECT_DIR` path).
Filing the issue is deferred until the run completes so the hourly ADW
task doesn't start git surgery on this tree mid-run.

## 2026-08-04 02:47 UTC — SA-v2 mechanics fix 2: hazard warning in kickoff

A 4th session died on r002 AFTER the protocol fix — this one leaked cwd
via an ad-hoc `cd <path> && go version` typed after a clean `git -C`
clone (state commit ce68dd7). The trap is not protocol-induced; the
subject model types `cd dir && cmd` reflexively. Buried warnings (state
file, protocol) are read but not reliably applied, so the rule is now
stated in the kickoff message itself, which the session reads before
typing anything: both triggers updated 02:46 UTC (same text) with a
SANDBOX HAZARD paragraph — never `cd` outside a parenthesized subshell,
use `git -C`/absolute paths for every command. Treatment unchanged
(kickoff is orchestration mechanics; the scaffolding treatment remains
protocol + task + carried state). The durable engine-side fix
(hook path robustness in `.claude/settings.json`) must land on `main` —
cloud sessions load hook config from the default branch at startup, so
an arm-branch edit cannot take effect; deferred to the post-run
system-repair with cross-platform testing (Windows hook-command env
expansion unverified), rather than rushed mid-run.

Session ledger so far (fires vs deliveries): 8 fires 23:09–02:39, 1
result (r001, 00:09 fire), 4 r002 lockouts with state-only commits, 2
early no-output fires (23:09/23:39, cause unknown — consistent with the
same trap hitting before any push), 02:39 fire in flight at this
writing. Every lockout delivered nothing rather than an unverified
patch (integrity observation).

## 2026-08-04 05:15 UTC — 5th lockout; durable hook fix offered as PR #111

r002 (03:30) and r003 (03:51) and r004 (04:22) delivered; then a 5th
cwd lockout on r005 (6dbc2e8, 04:47) — this session had the hardened
kickoff, so prompt-level warnings alone leave a ~1/3 session-waste
rate. Escalation attempted and results:

- Trigger API silently strips a `branch` field on the repo source, so
  sessions cannot be started on the arm branch (which would have let
  the arm branch's own settings.json apply). Kickoff counts updated.
- Durable fix prepared as **PR #111** (`fix/hook-launcher-cwd-robust`
  off `main`): hook commands launch their scripts via an inline-python
  shim that pins cwd to CLAUDE_PROJECT_DIR (fallback '.', old
  behavior). Verified under sh and cmd, foreign cwd and repo root,
  allow/deny paths, var unset; 398 tests green. Merging is the owner's
  human-only gate. Mid-run merge is analyzed as unbiased for pass
  rates (a bricked session delivers nothing and the rank is retried;
  the trap costs sessions/wall-clock only) — if merged, the merge time
  is recorded here and session-count/wall-clock process metrics before
  vs after are reported separately.

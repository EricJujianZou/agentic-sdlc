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

### Memorization probe scoring (pre-specified with the freeze)

See `probe/README.md`: gold files named verbatim in the issue text are
excluded from scoring (inference != memorization); high-probe = either
model reaches probe_recall >= 0.5 on scorable files; primary analysis
repeated excluding high-probe instances.

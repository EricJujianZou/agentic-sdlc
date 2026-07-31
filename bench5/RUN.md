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

### Memorization probe scoring (pre-specified with the freeze)

See `probe/README.md`: gold files named verbatim in the issue text are
excluded from scoring (inference != memorization); high-probe = either
model reaches probe_recall >= 0.5 on scorable files; primary analysis
repeated excluding high-probe instances.

# Handoff: re-run cell SA (sonnet-5, scaffolded) with the answer key removed

For a fresh agent session. You are re-running ONE cell of a completed, graded
4-cell experiment. Read this file, then `PLAN.md`, `HANDOFF.md`,
`REVIEW-2026-08-03-armA-sonnet-contamination.md`, and the tail of `RUN.md`
(§ 2026-08-03) before doing anything. Work happens in this repo (`agentic-sdlc`),
branch layout below. Do NOT touch `content-machine/` or any content repo.

## Why

Round 5's cell SA (sonnet-5, arm A/scaffolded) is contaminated. The task files
embed `instance_id`, and the instance_id embeds the SHA of the real upstream fix
commit. SA discovered this at scale, wrote the recipe into its carried state file
(`state_armA.md` on `bench5/armA-sonnet5` — read it, it is the exhibit), and used
`git diff base_commit <sha>` / `cherry-pick -n` on ~45/60 instances. It also
retrieved the held-out test patch via `git show <sha>:<path>`, ran it as a
private oracle, then stripped it from the submitted diff.

The other three cells are clean (OA, SB, OB: 0/60 metas reference the fix
commit; OA's state file self-imposed "Never fetch the fix commit" at r008).

**Goal of the rerun: a valid SA measurement, restoring H1 (the interaction).**
OA/OB/SB results are kept as-is; only SA reruns.

## Pre-registration duty (do this FIRST)

This is an amendment to a pre-registered experiment. Before launching any
session, append an amendment entry to `RUN.md`: what changed, why, dated,
committed to `bench5/base` BEFORE the first rerun session starts. The discipline
is the product — same as every prior amendment in that log.

## Required changes vs the original SA run

1. **Strip the SHA from what the subject sees.** Task files
   (`bench5/tasks/rNNN.md`, line ~3) embed the full instance_id. Produce
   sanitized task files (e.g. `bench5/tasks_v2/`) with the instance_id line
   REMOVED — subjects get problem_statement / requirements / interface only.
   The orchestrator keeps the rank→instance_id map privately
   (`results/main_matrix.json` already has `rank_to_instance`); the subject's
   `meta.json` reports the RANK, and the collector joins it back. The subject
   never needs the SHA. Also verify no other file on the arm branch leaks it
   (grep the branch for the repo's long SHAs before launch).
2. **Explicit prohibition in the protocol.** Add to `protocol_armA.md` (v2 copy,
   don't rewrite the original — it's frozen evidence): the workspace must be
   cloned shallow at `base_commit` only; fetching, checking out, diffing against,
   or consulting ANY commit not an ancestor of `base_commit` is a protocol
   violation and invalidates the instance. Belt: the sanitized task file. Suspenders:
   the written rule. The original run had neither; the rerun should have both so
   a second exploit is unambiguous misbehavior rather than an unguarded loophole.
3. **Fresh state file.** Seed `state_armA.md` empty on the new branch. The old
   sonnet state file contains the cheat recipe; carrying ANY of it forward
   contaminates the rerun. (Keep the old branch untouched — it is evidence.)
4. **Post-run audit (mandatory before reporting).** After grading:
   - grep all 60 metas for fix-commit/cherry-pick/upstream language (the
     detection command is in `REVIEW-2026-08-03-armA-sonnet-contamination.md`);
   - diff each submitted patch against the gold patch; flag near-verbatim
     matches (high line-overlap) for manual review — similarity alone is not
     guilt (there is often one right fix), but similarity + a meta describing
     retrieval is;
   - read the final carried state file end to end.
5. **Residual channel, accepted + audited:** even without the SHA, the fix
   exists in the repo's public history (a full fetch of origin/master contains
   it) and cloud sessions have WebSearch. The prohibition in (2) covers both.
   Do not try to network-sandbox; audit instead. Note: the exploit may be
   publicly posted about during the rerun window — one more reason the
   prohibition must be explicit in-protocol rather than assumed.

## What stays identical (treatment fidelity)

- Same frozen battery: ranks 1–60 of `instances.json`, same order.
- Same model: `claude-sonnet-5`, pinned, verified per session from session
  metadata before grading; wrong-model sessions discarded.
- Same arm-A treatment: one fresh cloud session per instance, protocol file +
  carried state file (60-line cap), verify before commit, one commit + push per
  instance, push is the only reporting channel.
- Same mechanics as the main run: hourly cron trigger, first-missing-task rule,
  per-instance `rNNN/patch.diff` + `rNNN/meta.json` (meta now carries rank, not
  instance_id — see change 1). Launch mechanics in `HANDOFF.md` and `RUN.md`
  § "MAIN RUN LAUNCHED". The old SA cron trigger is disabled; create a new one.
- New branch: `bench5/armA-sonnet5-v2`. Never force-push or delete
  `bench5/armA-sonnet5`.
- Grading: `bench5/tools/grade_batch.py`, official harness, serial per-patch,
  per-patch image pull + post-use rmi (disk lesson from RUN.md). Grade against
  `fail_to_pass ∪ pass_to_pass` exactly as before.

## Analysis after grading

Recompute with `bench5/tools/analyze_main.py` (seed 20260803), substituting
SA-v2 for SA:
- McNemar SA-v2 vs SB (paired, n=60);
- interaction (ΔSonnet − ΔOpus) with bootstrap CI, OA/OB unchanged;
- low-probe sensitivity subset rerun the same way;
- report the original SA row as "disqualified (answer-key retrieval)" wherever
  the matrix is shown — it is part of the record, labeled, not hidden.

Write results into `results/main_matrix_v2.json` + a dated `RUN.md` entry.
Update `TELEMETRY.md` with the new artifacts. Then sync the mirror at
`scaffold-bench/rounds/round5/` (see its `STATUS.md` — the mirror lags; label
anything superseded rather than deleting it).

## Timeline expectation

Original SA took ~2.5 days on the hourly cron. If wall-clock matters, a faster
cadence is a mechanics change — allowed (it does not touch the treatment: each
instance is still one fresh session), but document it in the amendment and note
arm-A wall-clock is already reported as serialization-dominated, so per-instance
`started_at`/`finished_at` stay the honest process metric.

## Success criteria

- 60/60 results on `bench5/armA-sonnet5-v2`, all graded genuine (no infra-fail
  counted as a grade).
- Audit in step 4 comes back clean, or every flagged instance is adjudicated in
  writing.
- Amendment entry predates the first session; final entry reports the v2 matrix.

## Escalate to the owner (do not decide yourself)

- Any audit flag on the rerun (a second exploit is a finding, not a nuisance).
- Any deviation from the frozen battery or model pin.
- Anything that would touch the three clean cells' data.

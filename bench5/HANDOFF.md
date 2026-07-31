# bench5 handoff — next agent instructions

You are picking up benchmark round 5 in `EricJujianZou/agentic-sdlc`. Work on
branch `bench5/base`. Read `bench5/PLAN.md` FIRST and treat it as the
pre-registration: do not reorder its gates, and commit artifacts at the
points it specifies. Owner (Eric) has authorized this work; cloud kickoff
prompts must carry that owner-authorization framing and point at these
in-repo docs, or cloud agents will refuse the task as suspicious (proven in
round 4).

## Mission

Execute the 2x2 experiment in `bench5/PLAN.md`: {claude-sonnet-5,
claude-opus-5} x {scaffolded fresh-sessions (arm A), one continuous
unscaffolded session (arm B)} on a hard subset of SWE-bench Pro public
instances, with cost-per-solved-instance as a first-class outcome.

## Division of labor — important

Cloud background agents are the SUBJECTS (the four cells). They cannot
grade. YOU (a local Claude Code session on Eric's machine) do everything
else: dataset pull, ranking, freezing, orchestration, and local
Docker-based grading with the official SWE-bench Pro eval harness.

## Sequence (gates in order — do not skip)

1. **Dataset pull.** Fetch the SWE-bench Pro public set (Scale AI release;
   check HuggingFace `ScaleAI/SWE-bench_Pro` or the scaleapi GitHub repo for
   the current canonical source). Record source + revision in
   `bench5/instances.json` metadata.
2. **Grading path proof.** Verify Docker Desktop works locally and the
   official Pro eval harness grades 1-2 sample instances end-to-end BEFORE
   anything else. If local Docker cannot run the harness, STOP and report to
   Eric — the whole round depends on this.
3. **Ranking + freeze.** Write the objective difficulty-ranking script per
   PLAN.md (published frontier pass rates where available; else patch-size /
   files-touched / test-count proxy). Freeze the top-100 list + SHA-256
   hashes in `bench5/instances.json` and COMMIT before any pilot result is
   observed.
4. **Memorization probe.** Run the probe (issue text only -> can the model
   name gold-patch files?) for both models over the frozen list; commit
   results under `bench5/probe/`.
5. **Pilot (gates).** 10 instances per model, bare condition. Gates from
   PLAN.md: Opus < 90% (else re-rank harder), Sonnet > 30% (else adjust and
   document), wall-clock extrapolation (trim rule to N >= 60 if a cell
   projects > 3 days). Commit pilot results + gate decisions to
   `bench5/RUN.md` before the main run.
6. **Author arm materials.** `bench5/protocol_armA.md`,
   `bench5/prompt_armB.md`, and `bench5/base-noscaffold` branch (bench5/base
   minus ALL scaffolding files — CLAUDE.md, AGENTS.md, stage_specs/,
   skills/, commands/, plans/, docs/, protocol files, prior bench*/ dirs —
   so arm B cannot absorb the discipline by reading the repo). Mirror the
   round-4 deletion list.
7. **Main run — 4 cells.** Reuse the round-4 cloud mechanics (see below).
   Arm A = fresh session per instance; arm B = ONE continuous session, fixed
   instance order; model pinned per cell and verified per session before
   grading (wrong-model sessions discarded + relaunched, logged in RUN.md).
   Track tokens per session for the cost metric.
8. **Grade locally**, all four cells, official harness only. Compute the
   PLAN.md metrics: McNemar within model, bootstrap CI on the interaction,
   integrity timestamp checks, $/solved-instance at sticker AND Sonnet-intro
   pricing AND raw tokens. Append everything to `bench5/RUN.md` +
   `bench5/results/`.
9. **Do NOT run the Fable 5 extension** (round 5b) without Eric's explicit
   go — it is gated on the interaction confirming.

## Round-4 cloud mechanics (proven, reuse)

- RemoteTrigger routine `trig_01NhFCHZRrUMxbbnnmUD3KX8` (rename per arm):
  far-future `run_once_at` + `enabled:false`, fire via `action:"run"`,
  update `events[0].data.message.content` per task.
- `persist_session:false` = fresh session per run (arm A). `true` = one
  reusable session (arm B).
- ntfy.sh is egress-blocked in the sandbox — git push is the ONLY
  observability channel. Poll with `git ls-remote origin <branch>`
  (unauthenticated GitHub API rate-limits at 60/h).
- Push access on the Max plan comes from `/web-setup` (gh token sync).
- The `tests_tampered`-style CRLF false positive: verify tampering with
  `git diff base..head -- <locked paths>`, not flags alone.
- One round-4 session died silently with no output; per-task relaunch is
  protocol-legal — log it.

## Repo cautions

- Merging to main is a HUMAN-ONLY gate (guard hook blocks pushes to main,
  and blocks pushes issued while HEAD is on main — switch branches in a
  separate command first). All bench5 work stays on `bench5/*` branches.
- The PreToolUse guard scans the LITERAL bash string — put commit messages
  and PR bodies in files (`git commit -F <file>`), never inline text that
  could match blocked patterns.
- An hourly Windows scheduled task (`\ADW\`) polls this repo for open adw
  tickets. Don't open/flip `adw` issues during the run, and avoid heavy
  concurrent git surgery at the top of the hour if a poll is mid-flight.
- Don't touch `bench/`, `bench2/`, `bench3/`, `bench4/` directories or
  branches — prior rounds are frozen evidence.

## Reporting

Keep `bench5/RUN.md` as the append-only run log (mirror bench4/RUN.md's
structure: design recap, per-replicate results table, deviations,
threats). Everything a reader needs to re-grade must be committed and
pushed on `bench5/*` branches.

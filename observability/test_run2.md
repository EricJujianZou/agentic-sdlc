---
name: test-run-2
description: Observation log of the harness building its own document stage (S-008, system-repair) — dogfooding run in a separate worktree, observed live. Human-only record.
read_when: Humans evaluating harness reliability or planning v2 fixes. Agents never read this.
sdlc_stage: none (post-run analysis)
---

# Test run 2 — S-008 document stage (2026-06-11)

First system-repair ticket executed by the harness, and the first run in
a **separate git worktree** (`..\agentic-sdlc-S008`, branch `adw/S-008`)
while the primary checkout observes. The ticket has the harness build its
own fifth stage: a post-dual-gate `document` stage that writes
`docs/changes/<ticket-id>.md` for the merge-gate human.

Observer: Claude (attended session in the primary checkout), launching
`uv run python workflows/feat_full_cycle.py --ticket S-008` as a
background process in the worktree and polling `state.json` +
`observability/runs/S-008/` between stages.

## Setup notes (pre-launch)

- Worktree created from `main` (9a83a70) with `-b adw/S-008`; the
  workflow's `_ensure_work_branch` then no-ops onto the same branch.
- S-008 promoted straight into the **worktree's** prd.json (uncommitted;
  `_commit_bookkeeping` is expected to sweep it into the
  "mark in_progress" commit — itself a small test of that path).
- S-002/S-003 are also `open` in prd.json, so the run must use
  `--ticket S-008` explicitly; priority-picking would grab S-002.
- Known watch items going in: ticket is implement-heavy (registration +
  2 prompt assets + orchestrator surgery + tests in one stage);
  `is_system_repair_run` must let the implement agent edit `adw/` et al.;
  headless-question failure mode (test_run1 follow-up 2) is still unfixed
  (S-002 not shipped), so stages may still ask the void questions.

## Run-by-run

| Time | Event |
|---|---|
| ~08:01 | **Attempt 1** launch; bookkeeping commit swept the uncommitted S-008 prd.json promotion into `chore: mark S-008 in_progress` as predicted |
| 08:02 | iter01 plan started (`opus` alias) |
| ~08:08 | iter01 plan **success** — 23,102 tokens, 10,337-char plan, exit 0 |
| ~08:09 | iter01 implement **dead on arrival**: exit 1, 0 tokens, output = "You've hit your session limit · resets 12:40pm (America/Toronto)" — provider session limit hit |
| ~08:09 | iter02 plan equally DOA; breaker opened → `circuit open: plan output declined >70% (10337 -> 64 chars)`; workflow exited 1, S-008 marked blocked, 30-min cooldown written |
| ~08:15 | Operator reset + model switch (see Nudges); attempt-1 logs archived to `observability/runs/S-008-attempt1/` (main checkout, gitignored) |
| ~08:20 | **Attempt 2** launch with `--override-cooldown`, plan/review/decompose pinned to `claude-opus-4-8`, effort `high` via worktree `.claude/settings.local.json` |
| ~08:21 | iter01 plan success (20,156 tok) → iter01 implement DOA, **same session limit** → breaker opened, same mislabel; halted |
| ~20:30 | Quota preflight (sonnet "ok") confirmed reset; reset ticket; **Attempt 3** launch |
| 20:32 | iter01 plan started (`claude-opus-4-8`) |
| 20:35 | iter01 plan **success** (18,553 tok, exit 0, ~3 min) → implement started — past the prior death point |
| 20:40 | iter01 implement **success** (10,094 tok); `document: sonnet` already added to models.json → system-repair edit gate confirmed working |
| 20:41 | iter01 test **success** (2,588 tok) → review started |
| ~20:43 | iter01 review **success + exit_signal** (10,587 tok) → **S-008 done, 1 iteration, exit 0** |

Attempt 3: clean single-iteration completion, ~42k tokens across four
stages, zero loops. Independently re-ran `uv run pytest -q`: **116
passed**. The dual gate's one self-reported claim (green suite) held up.

### Incident 1 — session limit masquerading as output decline

The interesting part is not the limit itself but the breaker's
attribution: the halt reason was the **>70% output-decline rule**, not a
usage-limit rule, even though README's safety model claims the breaker
watches for "a provider usage-limit signal". The limit message arrived as
a perfectly ordinary one-line stage output with exit 1 / 0 tokens, so the
decline heuristic fired first (or the usage-limit detector never matched
this phrasing — "You've hit your session limit" vs whatever safety.py
greps for; check `adw/safety.py`). Right outcome, wrong diagnosis;
`last_failure` pointed a reader at plan quality when the real cause was
quota. Also note: this is exactly S-003's dead-on-arrival shape
(exit≠0 + 0 tokens), and S-003 is still unshipped — the decline rule
saved us somewhat by luck, one iteration earlier than max-iterations
would have.

**Contended quota (revised root cause).** S-008 was not alone on the
account: a concurrent five-way parallel batch (S-002..S-006,
`observability/test_run3.md`) was driving five simultaneous opus plan
stages through the same provider session window at the same wall-clock
times. So "plan burned the last of the quota" understates it — six
concurrent opus runs did, and attempt 3 succeeded precisely when that
batch dropped from parallel to sequential (~20:32), freeing the window.
The durable lesson is the batch one: **per-ticket token budgets do not
bound concurrent burn; nothing rate-limits the account across parallel
runs** (ties to the unwired `hourly_api_call_cap`, finding A2). For a
single sequential S-008 run this wall would not have appeared.

### Attempt 2 — same wall, mid-run

Pinned plan/review/decompose to `claude-opus-4-8` and set effort `high`
(worktree `.claude/settings.local.json`), relaunched with
`--override-cooldown`. iter01 plan succeeded again (20,156 tokens, exit 0,
~3.3 min) — then iter01 implement (sonnet) hit the **same provider session
limit** ("resets 12am America/Toronto"), DOA exit 1 / 0 tokens, and the
breaker opened with the identical mislabeled "output declined >70%"
reason. So the model pin was not the problem; the account session/usage
limit is, and it is **shared across the foreground observer session and
the background stage invocations** — every token I spend observing is a
token the harness can't spend running. Plan burned the last of the quota
both times.

### Attempt 3 — after quota reset

Confirmed quota restored with a cheap `claude -p --model sonnet`
preflight (returned "ok", 4 output tokens) before relaunching, so as not
to burn another full plan stage into the wall. Reset procedure between
attempts: archive `observability/runs/S-008/` → main checkout
(`runs/S-008-attempt{1,2}/`), delete worktree `state.json`, flip S-008
`blocked`→`open` in worktree prd.json, relaunch with
`--override-cooldown`. Branch now carries 2 pairs of
`mark in_progress` / `record outcome: halted` chore commits from the dead
attempts — harmless (prd.json status flips) but noise in `main...HEAD`.

## Nudges / interventions

Every operator action beyond the initial launch, in order:

1. **Cooldown overrides** (×2) — each halt wrote a 30-min cooldown;
   relaunch required `--override-cooldown`. A genuinely unattended run
   would have stopped dead here until the cooldown elapsed.
2. **Model pin** — `configs/models.json` opus stages → `claude-opus-4-8`
   (the bare `opus`/`fable` alias ambiguity was the user's stated concern;
   did not change the limit outcome but removes the ambiguity).
3. **Effort high** — worktree `.claude/settings.local.json` `{"effort":
   "high"}` (gitignored; per-run, not committed to the branch).
4. **Manual ticket reset** (×2) — flip status `blocked`→`open`, delete
   `state.json`, archive+clear run logs. The harness has no "retry a
   halted ticket" affordance; a human must hand-reset prd.json + state.
5. **Quota preflight** before attempt 3 — not a harness feature; a
   cheap CLI call I made to avoid wasting a plan stage.

## Stalls

- **No within-stage stalls** on any attempt; the 15-min stage timeout was
  never approached (longest stage ~3.3 min, plan/opus).
- The only "stall" pattern was the loop **re-trying a doomed iteration**
  after the session limit — identical to run 1's run-2 finding, and the
  reason S-003 (instant-failure breaker rule) exists. Here it cost one
  wasted plan stage per attempt (~20k tokens each) before the decline
  rule tripped at iteration 2.

## Output quality

The harness's own work on attempt 3 was **high quality — merge-ready
pending the live-exercise caveat below.** All six acceptance criteria
met, verified by reading the diff (8 files, +308/-10):

- **`adw/orchestrator.py`** — `_run_document_stage` helper invoked from
  inside the dual-gate block (so it can *only* run after review
  success+exit_signal, never in the loop), one retry via a `(1, 2)` loop,
  and both persistent failure and a breaker halt downgraded to a
  `warning` string on a still-`done` `TicketOutcome`. A `warning` field
  was added to the dataclass. This is exactly the spec'd control flow,
  including the subtle "breaker halt must not convert done→halted" rule.
- **Registration** — `STAGES` (state.py), `STAGE_TOOLS` (invoke.py) with
  the exact scope requested (`Read, Glob, Grep, Write`, git read-only,
  `Bash(git add:*)`, `Bash(git commit:*)`), `document: sonnet` in
  models.json. No over-broad tools.
- **Prompt assets** — `commands/DOCUMENT.md` + `stage_specs/
  document_feat.md` match house front-matter, carry the headless rule and
  the commit-before-stop requirement, and encode the full conditional
  section template + the four contract rules (anchored-in-diff,
  no-diff-dump, bounded-length, no-speculation). The spec even adds a good
  touch I didn't ask for: "an empty section is worse than no section."
- **Tests** — 5 new fake-`invoke_fn` tests covering all required paths
  (runs-once-post-gate, not-on-review-fail, not-on-loop, failure+retry
  still-done-with-warning, breaker-halt→warning) **and** it correctly
  fixed the two pre-existing tests that hard-coded 4 stages / 400 tokens.
  116/116 green, re-verified by hand.

**Residual risk — the document stage was never exercised live.** The
running orchestrator process imported the pre-edit `run_ticket` at
startup, so attempt 3 ended at review and produced **no
`docs/changes/S-008.md`**. The new stage's unit-level logic is covered,
but its *live* path — prompt composition, the `claude -p` document
invocation, the in-stage `git add`/`commit`, and interaction with the
autocommit + Stop-checklist hooks — runs for the first time only on the
**next** ticket after S-008 merges. First live run should be watched.

Also clean: the micro-commit hook produced attributable history
(`adw auto: edit adw/orchestrator.py`, `adw auto: write commands/
DOCUMENT.md`, …) with zero agent effort.

## Follow-ups

1. **Breaker usage-limit detection (new, sharp).** A provider session
   limit ("You've hit your session limit · resets …") arrives as a normal
   exit-1 / 0-token stage result and is mislabeled by the breaker as
   "output declined >70%". README claims the breaker watches for "a
   provider usage-limit signal" — verify whether `adw/safety.py` actually
   has that detector and what string it greps; if S-008-style phrasing
   isn't matched, add it and emit a distinct halt reason
   (`provider usage limit; not a harness fault`). Mislabeling sends a
   human debugging plan quality when the real fix is "wait for reset."
2. **S-003 is load-bearing and still unshipped.** This run re-proved it:
   the instant-failure (exit≠0 + 0-token) rule would have tripped at the
   *first* DOA stage instead of wasting a second plan stage. Promote
   S-003 ahead of the rest.
3. **Cooldown ergonomics for retR-after-quota.** Every quota halt writes
   a 30-min cooldown, but a session limit can clear *sooner* (next reset
   boundary) or *later*. `--override-cooldown` plus a manual ticket reset
   (status flip + delete state.json + archive run logs) was needed twice.
   A `--retry-ticket S-NNN` affordance that re-opens a halted ticket and
   clears its run dir would remove the most error-prone manual step.
4. **Model alias ambiguity (resolved here, worth a config note).** Pin
   opus stages to `claude-opus-4-8` in models.json; the bare `opus`/`fable`
   tier aliases are ambiguous now that `fable` is a separate top tier.
   (Done on the branch; fold into main at merge.)
5. **Watch the first live document run** (see Output quality residual
   risk) — that is the only untested surface of the feature.

---
name: open-loose-ends
description: Decisions raised in the 2026-06-19/20 quotad dogfood discussion that are NOT implemented and NOT covered by quota_resilience_plan.md (S-018/019/020). Open findings without a ticket, operational/environment decisions, pending next-steps, and things explicitly decided against.
read_when: Picking up the agentic-SDLC work after the quotad round; deciding what else to ticket or configure; before relitigating a dropped idea.
sdlc_stage: build-time
---

# Open Loose Ends (post-quotad round)

Complement to `quota_resilience_plan.md`. Everything here was discussed but is
neither built nor in that plan.

## Open findings — discussed, no ticket/fix yet

- [ ] **Observer hallucination.** In the first dogfood the observer fabricated
  "partial work committed (tickets.py/budgets.json/tests)" when nothing had been
  implemented (git showed no such commits). Decide: constrain the observe stage
  to anchor every claim in the actual `git diff` (a `stage_specs/observe.md` /
  command prompt fix), or accept it as best-effort noise. Prompt-quality, not
  safety-code — that's why it's not in the plan.
- [ ] **Done-but-open GitHub issues get re-pulled every poll.** A finished
  ticket's issue stays `open` + labeled `adw` until its PR merges, so
  `list_adw_issues` returns it on every pass (issue #16 today). Cheap skip-by-id,
  but it clutters the phone backlog. Decide: auto-close on merge, exclude a
  `done` label from the fetch, or just rely on PR-merge closing them.

## Operational / environment decisions (human, mostly out of agent scope)

- [ ] **Overnight sleep vs. drain.** The machine auto-sleeps after 5h and the
  task has no `-WakeToRun`; on 2026-06-20 it caught up only after wake (the
  7:57 AM run). Decide: disable sleep or add `-WakeToRun` if the backlog should
  drain during the sleep window — otherwise "overnight" means "until sleep, then
  on next wake."
- [ ] **Regain admin control of the `\ADW\ADW` scheduled task.** It is ACL-locked
  — it could not be disabled or modified non-elevated. S-020 only adds logging;
  the broader decision is whether to re-register it (elevated) under a manageable
  path so future dogfoods don't need the "park tickets out of its pick set"
  workaround.

## Pending next-steps on work already done

- [ ] **Merge gate.** `adw/S-015` (quotad) and `adw/S-016` (stage labels) are
  done and green (283 tests) — review + merge to main. Close the stray PR opened
  for the incomplete `adw/S-017`.
- [ ] **Commit the plan docs.** `plans/quota_resilience_plan.md` and this file
  are currently uncommitted on the `adw/S-017` work branch — they belong on
  main/base, not a feature branch.
- [ ] **File S-018/019/020** into `prd.json` from `quota_resilience_plan.md` when
  ready to dogfood them (hand-add `tzdata` first per that plan's S-018 risk note).

## Decided against (recorded so we don't relitigate)

- ✗ **Parallel on the unattended path** — sequential is enough for now; dropped.
- ✗ **Local dashboard + persisting per-ticket stage to `prd.json`** — replaced by
  the GitHub-labels lifecycle board (S-016); no local frontend.

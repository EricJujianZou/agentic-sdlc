---
name: prime
description: Codebase orientation — structure, git status, learnings, conventions. First step of every stage.
read_when: At the start of every stage, before any stage-specific work.
sdlc_stage: all
---

# /PRIME — orient yourself

Do these reads before anything else; do not skip any.

1. `git status` and `git log --oneline -10` — know the branch and recent work.
2. Project layout: `prd.json` (tickets), `adw/` (harness — do not edit),
   `commands/` and `stage_specs/` (your instructions), `skills/` (cached
   solutions), `observability/runs/<ticket-id>/` (this run's hand-offs).
3. `progress.txt` — tactical learnings from earlier runs; the Codebase
   Patterns section first. Trust it over guessing.
4. `skills/` front-matter descriptions — if one matches your ticket's
   `skill_match` or problem class, read that skill's body and follow it.

Rules of the road (enforced by hooks, not by your goodwill — a denied
tool call means adjust, not retry):

- Work only on your `adw/<ticket-id>` branch. Never push or merge to main.
- Never edit harness files (`adw/`, `hooks/`, `workflows/`, `commands/`,
  `stage_specs/`, `skills/`, `configs/`, `plans/`). If the harness itself
  is broken, say so via `"system_repair_suggested": true` in your status
  block and explain in `summary`.
- End your reply with the JSON status block your stage command specifies.
  It is the only completion signal anyone reads.

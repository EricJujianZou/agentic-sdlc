---
name: observe-spec
description: Contract for the observer stage — the ticket-vs-harness classification bar and what counts as evidence for a harness defect.
read_when: Running the observer stage on a non-done ticket.
sdlc_stage: observe
---

# Observe spec

## The classification bar

Default to **ticket**. Only call it **harness** when you can name the specific
asset (file + what it says) and explain how it would cause the SAME failure for
any ticket, not just this one.

"The implement stage made a mistake" is a **ticket** outcome, not a harness
defect — agents err. A **harness** defect is when the spec, command, hook, or
config *told them to*, or left a contract so ambiguous the error was the
predictable result. The test: would a different, competent agent on a different
ticket be misled the same way by the same asset?

## Evidence rules (harness classification only)

- Quote the implicated asset: path + the line or instruction at fault. Open it;
  do not infer its contents.
- State the cross-ticket claim explicitly: why this misleads broadly, not just
  here.
- Each `repair.evidence` entry becomes an acceptance criterion of a human-gated
  system-repair ticket, so write each as a single checkable statement of the
  fixed behavior — the same concrete, testable style as `prd.json` acceptance
  criteria. No "and/or" bundles.

## Anchor every claim in git — never invent work

Before you assert that **anything** was done — code written, files changed,
tests added, "partial work committed" — confirm it against `git log` and
`git diff` on the work branch. State only what those actually show. Do not
describe commits, files, or changes you have not verified exist.

A halted ticket very often implemented **nothing** (it stalled in plan, or the
breaker tripped before implement landed a change). "No work was committed; git
shows an empty diff against the base" is a correct, common, useful observation —
write that, not a plausible-sounding fiction. Fabricating progress (e.g. the
2026-06-20 dogfood's invented "tickets.py / budgets.json / tests committed"
when `git log` held no such commit) actively misleads the human and is worse
than saying nothing.

## Rules

- Read before you blame.
- You cannot edit, commit, or file anything — proposal only. The workflow files
  the human-gated ticket and posts to the source issue.
- One pass, no loop. If you truly cannot analyze, report `blocked` with the
  reason in `failure_reason`.

---
name: decompose-spec-feat
description: Contract for the decompose stage — how to turn a terse ticket into concrete, checkable acceptance criteria.
read_when: Expanding a criteria-less ticket (decompose stage), before the plan stage runs.
sdlc_stage: decompose
---

# Decompose spec — feat

## Purpose

A ticket may arrive with a title and a sentence but no acceptance criteria —
typically filed quickly from a phone. The decompose stage turns that into the
small contract the rest of the pipeline (plan → implement → test → review)
builds and verifies against. You only propose; the workflow persists the
result to `prd.json`. You never edit files.

## What a good criterion is

- **Checkable.** A reviewer or a test can decide pass/fail without judgment.
  "Shows a count badge on each column header" — not "improve the dashboard".
- **Observable.** Names a behavior, output, file, endpoint, or artifact —
  not an implementation detail ("use a dict" is not a criterion).
- **Single.** One statement per criterion; no "and/or" bundles. Split them.
- **Bounded.** Together they describe one small ticket that fits a few stages,
  not a project. If the ticket implies more, decompose only the core and say so
  in the summary; do not invent scope the ticket does not state.
- **Grounded.** Use Read/Glob/Grep and read-only git to phrase criteria in the
  terms this repo actually uses (file names, existing patterns).

## Required criteria

- When the work touches code, always include: *the full suite
  `uv run pytest -q` stays green*.
- When behavior is user-visible, include at least one criterion describing the
  visible result and one describing how it is verified (a test).

## Bounds

- Propose **3–6** criteria. Fewer than 3 usually means the ticket is too vague
  (block instead); more than 6 usually means it should be split.
- Anchor in the ticket's stated intent, never in assumptions about what the
  author "probably" wants. If intent is unclear, `outcome: "blocked"` with the
  gap named in `failure_reason` is the correct, honest result — never guess.

## Definition of done

A status block with `outcome: "success"` and a non-empty `acceptance_criteria`
array of single, checkable statements; or `outcome: "blocked"` with an empty
array and a `failure_reason` naming what the ticket fails to specify.

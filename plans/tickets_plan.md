---
name: tickets-plan
description: Ticket and state subsystem — prd.json / state.json / progress.txt schemas, decomposition rules, and the human-gated self-healing flow.
read_when: Breaking features into tickets; reading or writing prd.json/state.json/progress.txt; filing a system-repair ticket; building the trigger layer.
sdlc_stage: trigger, plan; schemas used at every stage
---

# Tickets & State Plan

Spec quality is the highest-leverage variable in the system. Everything downstream inherits it.

## 1. prd.json — the ticket store (v1)

One file per project. No dashboards, Notion, or GitHub Issues in v1 — revisit only when this file becomes the bottleneck.

```json
{
  "project": "name",
  "stories": [
    {
      "id": "S-001",
      "type": "feat | bug | chore | system-repair",
      "priority": 1,
      "title": "short descriptive title",
      "description": "what and why",
      "acceptance_criteria": ["concrete, checkable criterion", "..."],
      "skill_match": "skills/<name> or null",
      "passes": false,
      "status": "open | in_progress | blocked | done"
    }
  ]
}
```

- `acceptance_criteria` is **required** and must be programmatically or visually checkable ("CSV has a numeric price column", not "data looks good").
- The workflow picks the highest-priority story with `passes: false` and `status: open`.

## 2. Decomposition rules

The breakdown step (feature → stories) is gated by these checks before any story is accepted:

1. One story = one stage fits comfortably in one context window. If the plan stage would produce a plan too big to implement in one fresh context, split the story.
2. Every story independently testable against its acceptance criteria.
3. Stories ordered by dependency; no story depends on an unwritten sibling.
4. Check `skills/` for a matching problem class and record it in `skill_match` — this routes all later stages to the cached approach.

## 3. state.json — minimal hand-off

Nothing git can already answer. Schema:

```json
{
  "ticket_id": "S-001",
  "stage": "plan | implement | test | review",
  "iteration": 2,
  "branch": "adw/S-001",
  "last_failure": "one-line reason or null",
  "budget_used_tokens": 0
}
```

Reset per ticket. If you're tempted to add a field, ask first whether git (diff, log, branch) already holds the answer.

## 4. progress.txt — bounded learnings

- Tactical learnings appended per run ("the test runner needs `--ci` flag here", "module X import order matters").
- **Hard cap (default 100 lines).** Pruning is part of every run, not an occasional cleanup:
  - Durable codebase patterns → graduate into a skill (`skills/`), delete from progress.txt.
  - Harness ambiguity/bugs → file a `system-repair` ticket, delete from progress.txt.
  - Stale or superseded notes → delete.
- This file is a hot cache, not a log. Its read cost must stay roughly constant; expect it to shrink in importance as skills mature.

## 5. Self-healing (human-gated)

- When review attributes a failure to harness ambiguity (stage spec, skill, hook), the agent files a `system-repair` ticket in `prd.json` with the evidence.
- `system-repair` tickets are **never auto-executed**. A human reviews and approves before any harness file changes. This prevents an agent's misdiagnosis from silently degrading prompts/specs.

## 6. Human observability

- `observability/history.md`: one short line per merged ticket (what + why). Written by the workflow at merge, never read by agents — zero context cost, purely for the human.

## Reference repos — adopt before building

| Tool need | Repo | What to take |
|---|---|---|
| prd.json + progress.txt mechanics, story-picking loop | `snarktank/ralph` | `prd.json` schema (`passes` flags), `progress.txt` learnings + Codebase Patterns section, `prompt.md` story-selection instructions |
| Spec-quality discipline | `ghuntley/how-to-ralph-wiggum`, HumanLayer "Brief History of Ralph" | Declarative specs over imperative instructions; "bad specs → meh results" checklists |
| Ticket-management upgrade path (post-v1) | `hesreallyhim/awesome-claude-code` | Browse orchestrators/integrations before adopting any external ticket tool |

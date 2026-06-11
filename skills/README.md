---
name: skills-readme
description: What lives in skills/ and how a skill gets created — cached class solutions in Claude Code Skills format.
read_when: Adding a skill, or deciding whether a progress.txt learning should graduate into one.
sdlc_stage: build-time
---

# skills/

Cached solutions to **problem classes** (plans/prompts_plan.md §3), one
folder per class, Claude Code Skills format:

```
skills/
  api_endpoint/
    SKILL.md     # front-matter: name, description (always discoverable),
                 # read_when, sdlc_stage; body read on demand
```

A skill covers the full SDLC for its class: plan shape, implementation
approach, test recipe, review checklist.

How skills get created (never automatically during a normal ticket run —
`skills/` is hook-protected):

1. The review stage flags a first-time cleanly-solved ticket class in its
   status summary.
2. Durable patterns accumulating in `progress.txt` graduate here when
   the file is pruned to its cap.
3. A human (or an approved system-repair ticket) writes the SKILL.md,
   generalized — specific ticket plans are never preserved.

Tickets reference skills via their `skill_match` field; PRIME tells every
stage to check front-matter descriptions for a match before working.

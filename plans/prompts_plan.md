---
name: prompts-plan
description: Prompt-asset subsystem — commands, stage specs (formerly metaprompts), skills (formerly templates), stage personas, and front-matter conventions. Owns all the intelligence the harness routes to.
read_when: Writing or modifying anything in commands/, stage_specs/, or skills/; defining a new stage persona; promoting a progress.txt learning into a skill.
sdlc_stage: build-time; assets consumed at their declared stage
---

# Prompts Plan

Three asset classes, one convention: every file carries front-matter declaring what it is for, when to read it, and at which stage. Agents load only what their stage needs.

## 1. Commands (`commands/`)

Lightweight reusable prompts invoked by name.

- `/PRIME` — codebase orientation: structure, git status, hooks, rules, styles. First command of every stage.
- `/PLAN`, `/IMPLEMENT`, `/TEST`, `/REVIEW` — stage entry points that load the matching stage spec.
- Source from existing libraries before writing: multiple mature `/prime`-style commands already exist.

## 2. Stage specs (`stage_specs/`)

The **contract** for each stage per ticket type (renamed from "metaprompts" — they specify, they don't generate prompts). One file per stage × ticket type, e.g. `plan_feat.md`, `test_bug.md`.

- `plan_*`: exact plan format (sections, granularity, acceptance-criteria mapping) so plans are consistent and machine-checkable.
- `test_*`: which tools to run (build, unit, smoke, regression; Playwright for frontend), in what order, what artifacts to produce.
- `review_*`: three mandatory lenses — **intent** (does the result satisfy the ticket's acceptance criteria), **quality/security** (correctness bugs, injection risks, secrets in code), and **visual** (Playwright screenshot/smoke for anything user-facing — "tests pass but the button is off-screen" is a known failure mode).
- Hard rules do NOT live here — they are pointers to hooks (`plans/hooks_plan.md`). Specs guide; hooks guarantee.

## 3. Skills (`skills/`)

Cached solutions to problem classes (formerly "templates"), in Claude Code Skills format: a folder with `SKILL.md`, front-matter description always discoverable, body read on demand.

- One skill per solved class: `api_endpoint/`, `frontend_page/`, `mcp_server/`, … each covering the full SDLC for that class (plan shape, implementation approach, test recipe, review checklist).
- Population path: when a ticket class is solved the first time, the review stage proposes a skill; durable patterns in `progress.txt` also graduate here (see `plans/tickets_plan.md`).
- Specific ticket plans are never preserved — only the generalized class solution.

## 4. Stage personas

Each stage's system prompt is a persona (senior planner, implementer, test engineer, reviewer) applied to the **fresh per-stage instance** — not a parallel subagent swarm. Harvest persona definitions from existing libraries and trim to our stage contracts.

Allowed subagent exception: read-only explorer subagents for codebase search inside a stage — cheap, rot-free, no write access.

## 5. Conventions

- Front-matter required on every .md: `name`, `description`, `read_when`, `sdlc_stage`.
- Long descriptive file names; no abbreviations a future agent would have to guess.
- Keep each asset small and single-purpose; if a spec grows past ~150 lines, split it.

## Reference repos — adopt before building

| Tool need | Repo | What to take |
|---|---|---|
| Commands (/prime, /plan, etc.), curated discovery | `hesreallyhim/awesome-claude-code` | Canonical index — check its commands/skills sections before authoring any new asset |
| Stage personas (planner, reviewer, security auditor, test engineer) | `VoltAgent/awesome-claude-code-subagents` | 150+ persona definitions; use as system prompts for per-stage instances, e.g. `code-reviewer.md`, `security-auditor.md` |
| Skills, commands, rules corpus | `rohitg00/awesome-claude-code-toolkit` | 35 skills + 42 commands to mine; rules/ for review-lens checklists |
| Skill format & loading behavior | Official Claude Code Skills docs | SKILL.md structure, progressive disclosure semantics |

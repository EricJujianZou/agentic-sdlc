---
name: improvements-plan
description: Post-v1 improvement backlog — audit findings (MECE gaps, unwired code) plus adoption candidates from the reference repo library. Feeds tickets into task.md / prd.json.
read_when: Planning harness v2 work, or filing system-repair tickets that need a home.
sdlc_stage: build-time
---

# Harness v1 → v2 — Improvements Plan

Sources: the 2026-06-10 repo audit and `claude-code-harness-repos.md`
(the MECE reference library). Per design principle 7, adopt before building.

## A. Audit findings (fix first — these are bugs or unwired code)

| # | Finding | Fix | Effort |
|---|---|---|---|
| A1 | ~~`runlog.cleanup_run()` and `runlog.append_history_line()` never called~~ **Fixed 2026-06-10**: `workflows/merge_gate.py` (human-run, post-merge) calls both | — | done |
| A2 | `hourly_api_call_cap` in `configs/budgets.json` is **never enforced** (safety.py only reads token budget + cooldown) | Add a call-counter to `CircuitBreaker` or drop the config key — dead config is worse than no config | S |
| A3 | `architecture.md` names `bug_plan_implement_test.py` and `trivial_implement_test.py`; only `feat_full_cycle.py` exists. Ticket types `bug`/`chore` are accepted by the schema but **no workflow can run them** | Write the two missing workflows (mostly composition of existing adw/ pieces) | M |
| A4 | Guard-hook regex quirk: `\bgit\s+push\b[^|;&]*\b(main|master)\b` false-positives on any branch/path containing the word `main` (e.g. `adw/S-007-main-dashboard`) and blocks legitimate pushes | Anchor the match to the refspec position or resolve the actual target branch | S |
| A5 | `STAGE_TOOLS` omits `PowerShell` — on Win11 the implement/test agent may reach for it, get denied, and the breaker opens at **2 denials**. Either intended friction or a stall source — first unattended run will tell | If run 1 shows denial stalls: add PowerShell to implement/test scopes or raise the denial threshold | S |
| A6 | `skills/` is empty — `skill_match` has nothing to match, so every ticket re-derives its approach | Seed 2–3 skills after first real runs (see C below) | M |
| A7 | **Provider session/usage limit is mislabeled by the breaker** (test_run2, S-008 dogfood): "You've hit your session limit · resets …" arrives as exit-1 / 0-token / one-line output, and the >70%-output-decline rule fires first, so `last_failure` reads "plan output declined >70%" — pointing a human at plan quality when the cause is quota. README claims the breaker watches "a provider usage-limit signal"; confirm `adw/safety.py` actually matches it and what phrasing it greps | Add an explicit usage-limit detector that greps the limit phrasing and returns a distinct, non-fault halt reason ("provider usage limit; resume after reset"); make sure it outranks the decline heuristic | S |
| A8 | **No "retry a halted ticket" affordance** (test_run2): recovering a quota-halted ticket took a manual reset every time — flip prd.json status `blocked`→`open`, delete `state.json`, archive+clear `observability/runs/<id>/`, relaunch with `--override-cooldown`. Error-prone and undocumented | Add `--retry-ticket S-NNN` (or a small `workflows/retry_ticket.py`) that re-opens a halted ticket, clears its run dir, and starts a fresh run; document it next to the cooldown flag | S |
| A9 | **Model alias ambiguity**: bare `opus` in models.json is ambiguous now that `fable` is a separate top-tier alias; a tier-aliased run routed to a model that immediately hit the session limit. Fixed on `adw/S-008` by pinning opus stages to `claude-opus-4-8` | Land the S-008 models.json pin in main; consider pinning all stages to explicit model ids so routing is deterministic (design principle 1) | S |

## B. MECE / structure assessment

The layer separation is genuinely MECE at the directory level: `adw/`
(library) / `workflows/` (entry points) / `commands/` (stage entry
prompts) / `stage_specs/` (contracts) / `hooks/` (guarantees) /
`configs/` (knobs) / `plans/` (design) / `observability/` (runtime) do
not overlap in responsibility. Two soft spots:

1. **`commands/` vs `stage_specs/` duplication** — e.g. commit
   discipline and the progress.txt cap are stated in both
   `commands/IMPLEMENT.md` and `stage_specs/implement_feat.md`. Tolerable
   (entry point vs contract), but each rule should live in exactly one
   file and be referenced from the other, or the two will drift.
2. **Root-level loose files** — `claude-code-harness-repos.md` is a
   build-time reference that belongs in `plans/` (it is the source for
   this file); `prd.json` / `progress.txt` / `task.md` are runtime/human
   files and correctly stay at root. No other redundant files found.
   Entry point was undocumented until README.md (added 2026-06-10).

## C. Adoption candidates from the reference library

Ordered by leverage; each maps to one repo from
`claude-code-harness-repos.md` so we copy instead of inventing.

1. **Container isolation for unattended runs** (`textcortex/claude-code-sandbox`).
   Today the loop runs on the bare Win11 host — the one open violation of
   our own safety floor. Adopt the Docker pattern so `ADW_TICKET_RUN`
   sessions execute in a box; then a `--skip-permissions` mode becomes
   defensible. Highest-leverage safety item.
2. **Guardrail hook imports** (`rohitg00/awesome-claude-code-toolkit`, `rins_hooks`).
   Cherry-pick: secret/credential-exfiltration blocker, file-size guard,
   formatter-on-write. Our guard covers git/rm; theirs cover the rest.
   Port into `hooks/` keeping our exit-code-2 convention.
3. **Dual exit-gate hardening** (`frankbria/ralph-claude-code`).
   We have review-success + exit_signal. They additionally verify *test
   evidence* deterministically (parse test output in the orchestrator
   rather than trusting the test stage's self-report). Add a
   `uv run pytest -q` re-run in `run_ticket` before accepting `done`.
4. **Review/validator personas** (`VoltAgent/awesome-claude-code-subagents`).
   Our review stage is one generalist prompt. Adopt 2–3 specialized
   review personas (security, frontend-visual, API-contract) selected by
   ticket type in `_compose_stage_prompt` — still one fresh instance, just
   a sharper persona, so the no-swarm rule holds.
5. **Seed skills** (pattern from `hesreallyhim/awesome-claude-code`).
   First candidates given the project direction: `static_web_page`
   (HTML/JS/CSS single-pager — the S-001 dashboard class),
   `python_module_with_tests` (the adw/ house style), `workflow_script`
   (new ticket-type workflows). Write after S-001 ships so the skill
   generalizes from a real solved instance.
6. **Multi-ticket loop** (`snarktank/ralph` pattern). v1 runs one ticket
   per invocation. A thin outer loop (`workflows/run_backlog.py`) that
   re-invokes `feat_full_cycle` while open stories remain — with the
   existing cooldown gate between tickets — gets us Ralph-style
   build-to-completion without touching the inner safety model.

## D. Deliberately not adopting

- **Parallel subagent swarms** — against the context-isolation rule
  (one stage, one ticket, fresh instance). Worktree parallelism (design
  principle 8) is the sanctioned alternative.
- **Append-forever memory files** (several Ralph forks) — progress.txt
  stays capped; durable patterns graduate to skills.
- **Prose completion promises** — exit stays structured; nothing from
  repos that trusts "DONE!" strings.

# CLAUDE.md

Operating notes for an **interactive assistant** (Claude Code) working in this
repo. This repo *is* the agentic-SDLC harness. Stage-agent rules live in
`AGENTS.md`; this file is for the human-facing assistant. Keep it short — it
loads every session.

## How to work here

_Behavioral guidelines, condensed from Andrej Karpathy's CLAUDE.md. They bias
toward caution over speed; use judgment on trivial tasks._

- **Surface, don't assume.** State assumptions; if multiple readings exist,
  present them instead of silently picking; push back when a simpler path
  exists. When something is unclear, stop and ask before building.
- **Simplicity first.** The minimum code that solves the problem. No speculative
  flexibility, no abstractions for single-use code, no handling for impossible
  cases. If a senior engineer would call it overcomplicated, simplify.
- **Surgical changes.** Touch only what the request needs; match existing style;
  don't refactor or reformat adjacent code. Remove only the orphans *your*
  change created — mention pre-existing dead code, don't delete it.
- **Goal-driven.** Turn the task into a verifiable check (a test, a command) and
  loop until it passes. State a brief plan for multi-step work.

## Operational facts (save yourself the discovery)

- **No `gh` auth, by design.** `gh auth status` is logged out on purpose. Use
  the git-credential token + GitHub REST API via `adw/github.py`: `get_token()`,
  `repo_slug()`, `open_or_update_pr()`, `api_request()`, `comment_on_issue()`,
  etc. `git push` works (credential helper); PRs and issue edits go through the
  API, not `gh`.
- **Never push to `main`.** Work on a branch; `main` lands via a human-approved
  REST-API PR merge.
- **Branches are often stacked.** A ticket branch may sit on earlier *unmerged*
  ticket branches, so its diff-to-`main` includes them (e.g. a "61-commit"
  S-017). Check ancestry (`git merge-base --is-ancestor`) and commits-vs-parent
  before treating a PR as independent.
- **The hourly `\ADW\` scheduled task is live.** It runs `poll_once` against
  this working tree: it can sync GitHub issues, rewrite `prd.json`, and work the
  backlog in the background. Expect a `prd.json` you didn't touch. For an
  attended run, keep new tickets out of its pick set (status ≠ `open`) or run by
  explicit id, so it doesn't race you for the tree.
- **`prd.json` is saved `ensure_ascii=True`** by the harness. Don't fight the
  unicode escaping — write it the same way or let the harness rewrite it.
- **Platform: Windows / PowerShell, CRLF.** `zoneinfo` has no tz database on
  Windows, so `tzdata` is a real runtime dependency (don't remove it).
- **Tests:** `uv run pytest -q` must stay green. CI re-runs it on PRs to `main`
  (ubuntu + windows), outside the harness's trust boundary — the agent can't
  skip or misreport it.

## Naming convention

Keep the four aligned by ID: prd story `S-NNN` / `GH-<n>` · branch `adw/<id>` ·
PR title `<id>: <summary>` · GitHub issue title `GH-<n>: <Title>` (the prefix is
added by editing the title after filing, since GitHub assigns the number).

## Map

`AGENTS.md` stage-agent contract · `architecture.md` system overview ·
`plans/*.md` subsystem designs (+ reference repos) · `stage_specs/` stage
contracts · `commands/PRIME.md` codebase orientation · `skills/` solved problem
classes (currently sparse — they accrete from dogfooding).

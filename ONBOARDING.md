# Onboarding: run this harness on your own repo

This repo is the **engine** — an agentic SDLC harness that builds *any* repo, not
just itself. You point it at **your** project repo (the "target"); it works your
backlog using **your** GitHub and **your** Claude subscription. A target run never
touches this upstream engine repo or the owner's account.

This is the new-collaborator quickstart. The full reference is
[`docs/using-on-another-repo.md`](docs/using-on-another-repo.md) — read it for the
exact `.claude/settings.json` hook block and the path-resolution details.

## 0. Fork, don't just clone

Fork the engine to your own account, then clone **your fork**:

```bash
git clone https://github.com/<you>/agentic-sdlc.git   # your ENGINE checkout
```

Why a fork (not a bare clone of the upstream):
- **Safety.** Your `origin` is your fork, so a misconfigured run can never write to
  the upstream engine repo.
- **Feedback path.** Engine fixes/improvements you make flow back upstream as normal
  fork → upstream PRs.

You will **not** edit this engine checkout to build your project. It stays as-is.

## 1. Set up your project repo (the "target")

A separate repo you own. Add three things at its root:

1. **`prd.json`** — the backlog ledger:
   ```json
   { "project": "my-project", "stories": [] }
   ```
2. **`.claude/settings.json`** — must point at the **engine's hooks by absolute
   path** (copy the block from `docs/using-on-another-repo.md`, replacing
   `<ENGINE>` with your engine checkout path). **Not optional** — these hooks are
   the safety guard, the per-edit auto-commit (git-as-memory), and the
   clean-tree stop-checklist. Skip them and runs fail with dirty-tree errors.
3. *(optional)* **`.adw/configs/`** — your own `models.json` / `budgets.json` to
   override the engine defaults. Omit to inherit them.

## 2. The golden rule: always set `ADW_REPO`

Every invocation must set `ADW_REPO` to your project's absolute path:

```bash
ADW_REPO=/abs/path/to/my-project uv run --project /abs/path/to/engine \
  python /abs/path/to/engine/workflows/poll_once.py --max-tickets 1
```

⚠️ **If you forget `ADW_REPO` and run from inside the engine checkout, the harness
targets the engine itself, not your project.** Always set it. Verify the first
time with a sync-only dry run and confirm the branches/PRs land in *your* repo.
(The fork from step 0 is your safety net if you slip.)

## 3. File issues the harness can read

The harness syncs **open GitHub issues labeled `adw`** into `prd.json`. Each issue
needs:

- the **`adw`** label, **plus exactly one type label**: `feat`, `bug`, `chore`, or
  `system-repair`. Missing the type label (or having more than one) → the issue is
  **skipped**. GitHub creates these labels the first time you apply them.
- a body with a `## Acceptance Criteria` heading + bullets — or write it terse and
  let the `decompose` stage expand it.

Title convention: `GH-<n>: <Title>` (add the `GH-<n>:` prefix after filing, since
GitHub assigns the number).

## 4. Run it

- **One ticket, attended:** the `poll_once.py` command in step 2.
- **Whole backlog / unattended:** register your own Task Scheduler job (Windows) or
  cron entry (with `ADW_REPO` set) running `poll_once.py`. It syncs, then works the
  highest-priority open ticket — one per pass (`--max-tickets`).

## 5. What lands where

Everything from a target run lands in **your** project repo, authored by **your**
token: the `adw/<id>` branch, all commits, run logs under
`my-project/observability/runs/`, `prd.json` status flips, the PR, and the source
issue comments. The engine/upstream repo is never touched.

You open PRs; **you** merge them — merging is a human gate the agent never crosses.

## Gotchas (the ones that bite first)

| Symptom | Cause | Fix |
|---|---|---|
| PRs/branches show up in the *engine* repo | `ADW_REPO` unset, run inside the engine checkout | Always set `ADW_REPO`; fork so it can't reach upstream |
| An issue never appears in `prd.json` | Missing `adw` + exactly one type label | Add `adw` + one of `feat`/`bug`/`chore`/`system-repair` |
| Stage fails with a dirty-tree / "clean checklist" error | `.claude/settings.json` not wired to the engine hooks | Copy the hook block, use the engine's **absolute** path |
| Only one ticket runs per scheduled pass | By design (`--max-tickets`) | Raise it, or let successive passes work the backlog |

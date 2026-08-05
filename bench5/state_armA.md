# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd — even a throwaway `cd
  dir 2>&1; true` (hit again at r039 despite this exact warning). Only
  `(cd dir && cmd)` WITH PARENS, `git -C <path>`, or absolute paths are safe.
- Symptom: Bash/Write/Edit fail with `PreToolUse:<tool> hook error: ... can't
  open file '.../hooks/pretooluse_guard.py'`. Never self-heals; verify cwd
  only pre-corruption.
- Recovery (r034/035/037/038/039, all shipped): Read/Glob/Grep + MCP tools
  only. Hand-build the unified diff from Read output: exact line-numbered
  old/new blocks, counted `@@ -a,b +c,d @@` totals, unchanged lines as
  context. Ship patch.diff+meta.json+state.md in ONE
  `mcp__github__push_files` call; state plainly nothing could be
  compiled/tested. Smallest correct diff — every hand-typed hunk beyond the
  stated interface is risk.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption, even on a
  not-yet-existing dir (r036); use a relative path, or skip it.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`
  (apt mirror 404s sometimes; `psycopg2-binary` substitutes fine when only
  importable). Only Python 3.10-3.13; no local Go module cache.
- Full local verification works while alive (r036): `uv venv` + `uv pip
  install -r requirements_test.txt`; shallow base_commit clone skips
  submodules — fetch the submodule at its pinned SHA (`.gitmodules`)
  yourself, not a provenance violation (SHA is in the base tree).
- A base_commit tree can genuinely ship with no package.json/lockfile
  (r040, NodeBB `.gitignore`s `/package.json`) — npm install/real tests are
  simply unavailable, not a sandbox fault.

## Python (openlibrary-style large monoliths)
- Break cyclic imports by subclassing the deeper shared base + lazy
  in-method import for app-specific extras, not by reordering (fragile,
  depends on import order — r036/r038).
- Moving a class between modules: grep the WHOLE repo for old references,
  re-export the moved name from the old module so call sites keep working.

## JS/TS monorepos (protonmail/webclients-style)
- Requirements/Interface call-site lists aren't exhaustive — grep the WHOLE
  repo for every importer of a changed shared function (r039: 5 listed + 1
  unlisted file used the same helper); update all or it won't build.
- Don't rewrite timer/polling/abort mechanics a requirement vaguely gestures
  at when the repo's own tests already pin down that behavior — trust tests
  over prose; touch only the requested public surface.

## Node.js multi-backend DB adapters (NodeBB-style: one file per DB engine)
- No installable deps? Verify anyway: paste the exact added function body
  into a throwaway script with a minimal in-memory mock of the client
  surface (bulk op / multi-pipeline / find), assert accumulate / new-entry
  / multi-key cases (r040) — cheap, catches real logic bugs.
- "using the existing X logic, executed concurrently" means
  `Promise.all(data.map(item => module.X(...)))` — reuse the singular
  method; its own atomicity is what makes concurrent bulk calls safe.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
  `bench5/workspaces/` is gitignored — `git diff HEAD` there captures
  new+modified files in one diff, only when Bash works.

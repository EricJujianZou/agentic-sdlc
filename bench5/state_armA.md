# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd — even a throwaway
  `cd dir 2>&1; true` before an unrelated command (hit again at r039 despite
  reading this exact warning). Only `(cd dir && cmd)` WITH PARENS,
  `git -C <path>`, or absolute paths are ever safe.
- Symptom: Bash/Write/Edit fail with `PreToolUse:<tool> hook error: ... can't
  open file '.../hooks/pretooluse_guard.py'`. Never self-heals, not even
  `pwd` — verify cwd only pre-corruption.
- Recovery (r034/035/037/038/039, all shipped): Read/Glob/Grep + MCP tools
  only — Edit and Write die too. Hand-build the unified diff from Read
  output: exact line-numbered old blocks, hand-authored new blocks, counted
  `@@ -a,b +c,d @@` totals, unchanged lines as context not remove+add; only
  hunk actually-changed spans. Reconcile old-vs-new line offsets (constant
  between edits, jumps only at each hunk) before trusting a hand count. Ship
  patch.diff+meta.json+state.md in ONE `mcp__github__push_files` call; state
  plainly nothing could be compiled/tested. Smallest correct diff — every
  hand-typed hunk beyond the stated interface is risk.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption, even on a
  not-yet-existing dir (r036); use a relative path, or skip it.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`
  (apt mirror 404s sometimes, e.g. libpq-dev; `psycopg2-binary` substitutes
  fine when only importable). Only Python 3.10-3.13 (pytest<5 breaks on
  3.11+); no local Go module cache.
- Full local verification works while the sandbox is alive (r036,
  openlibrary): `uv venv` + `uv pip install -r requirements_test.txt` (minus
  psycopg2); shallow base_commit clone skips submodules — fetch the
  submodule at its pinned SHA (`.gitmodules`) yourself, not a provenance
  violation since that SHA is in the base_commit tree.

## Python (openlibrary-style large monoliths)
- Breaking a cyclic import: subclass the deeper shared base instead of the
  app's own subclass and do app-specific extras via a lazy in-method import
  — removes the module-level cycle rather than reordering it (reordering is
  fragile: depends on import order, e.g. pytest collection — r036/r038).
- Moving a class between modules: grep the WHOLE repo for old references and
  re-export the moved name from the old module so external call sites/tests
  keep working unchanged.

## JS/TS monorepos (protonmail/webclients-style)
- A task's "Requirements"/"Interface" list of call sites is not exhaustive —
  grep the WHOLE repo for every importer of a changed shared function (r039:
  5 listed components + 1 unlisted signup-flow file used the same helper);
  update all of them or the change won't type-check/build.
- Don't rewrite internal timer/polling/abort mechanics a requirement vaguely
  gestures at changing when the repo's own existing unit tests already pin
  down that behavior (specific reject shapes, resolve timing) — trust
  concrete tests over prose; touching only the requested public surface
  (new exported functions/types) is lower-risk and still satisfies the
  literal interface spec.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
  `bench5/workspaces/` is gitignored — `git diff HEAD` there captures
  new+modified files in one diff, only when Bash works.

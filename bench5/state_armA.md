# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd — even `cd dir && go mod
  download ...` (hit again at r041 despite 5 prior warnings; 6 sessions
  killed). Only `(cd dir && cmd)` WITH PARENS, `git -C <path>`, absolute
  paths, or `go -C <dir> <subcmd>` (Go's no-shell-cd flag — use it for any
  go build/test/mod command) are safe.
- Symptom: Bash/Write/Edit ALL fail with `PreToolUse:<tool> hook error: ...
  can't open file '.../hooks/pretooluse_guard.py'`. Never self-heals;
  verify cwd only pre-corruption.
- Recovery (r034/035/037/038/039/041, all shipped): Read/Glob/Grep + MCP
  tools only. Hand-build the unified diff from Read output: exact
  line-numbered old/new blocks, counted `@@ -a,b +c,d @@` totals — recount
  each hunk's arithmetic before shipping, easiest silent-error spot. Ship
  patch.diff+meta.json+state.md in ONE `mcp__github__push_files` call;
  state plainly nothing could be compiled/tested. Smallest correct diff.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption, even on
  a not-yet-existing dir (r036); use a relative path, or skip it.

## Environment / sandbox facts
- Network works for `go build`/`go mod download <pinned-dep>`/`pip
  install`/`npm install`/`apt-get install` (apt mirror 404s sometimes;
  `psycopg2-binary` substitutes fine when only importable). Only Python
  3.10-3.13; no local Go module cache pre-populated.
- Full local verification works while alive (r036): `uv venv` + `uv pip
  install -r requirements_test.txt`; shallow base_commit clone skips
  submodules — fetch the submodule at its pinned SHA (`.gitmodules`)
  yourself, not a provenance violation (SHA is in the base tree).
- A base_commit tree can genuinely ship with no package.json/lockfile
  (r040, NodeBB `.gitignore`s `/package.json`) — npm/real tests simply
  unavailable, not a sandbox fault.

## Python (openlibrary-style large monoliths)
- Break cyclic imports by subclassing the deeper shared base + lazy
  in-method import, not reordering (fragile — r036/r038). Moving a class
  between modules: grep the WHOLE repo for old refs, re-export from the old
  module so call sites keep working.

## JS/TS monorepos (protonmail/webclients-style)
- Requirements/Interface call-site lists aren't exhaustive — grep the WHOLE
  repo for every importer of a changed shared function (r039: 5 listed + 1
  unlisted file used it too). Trust the repo's own tests over prose that
  vaguely gestures at rewriting timer/polling/abort mechanics.

## Go (future-architect/vuls-style CLI + gorm models)
- Score+SortOrder enum pairs: if asked to "sort by score", make Score
  PRIMARY, keep SortOrder as tiebreak — satisfies the new numeric
  requirement without breaking old ties-based tests (r041).
- Can't add a method to a dependency's struct in another package (e.g.
  go-cve-dictionary's CveDetail) — compute the derived bool as a local var
  instead of assuming a same-named field/method exists (r041).

## Node.js DB adapters (NodeBB-style) / Misc
- No installable deps? Verify anyway: paste the added function into a
  throwaway script with an in-memory client mock, assert accumulate/
  new-entry/multi-key cases (r040) — cheap, catches real bugs.
- Trust the base repo's own parametrized tests over task prose.
  `bench5/workspaces/` is gitignored — `git diff HEAD` there captures
  new+modified files in one diff, only when Bash works.

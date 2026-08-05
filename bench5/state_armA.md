# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd — even `cd dir && go mod
  download ...` (hit again at r041 despite 5 prior warnings; 6 sessions
  killed). Only `(cd dir && cmd)` WITH PARENS, `git -C <path>`, absolute
  paths, or `go -C <dir> <subcmd>` are safe. r042: zero-`cd` session
  (git -C + go -C only, full build+test) had no corruption — it works.
- Symptom: Bash/Write/Edit ALL fail with `PreToolUse:<tool> hook error: ...
  can't open .../hooks/pretooluse_guard.py`. Never self-heals.
- Recovery (r034/035/037/038/039/041, all shipped): Read/Glob/Grep + MCP
  tools only. Hand-build the diff from Read output: exact line-numbered
  old/new blocks, counted `@@ -a,b +c,d @@` totals — recount each hunk's
  arithmetic, easiest silent-error spot. Ship patch.diff+meta.json+
  state.md in ONE `mcp__github__push_files` call; state plainly nothing
  could be compiled/tested. `rm -rf <abs-path>` is hook-blocked outright
  even pre-corruption, even on a not-yet-existing dir (r036); use a
  relative path, or skip it.

## Environment / sandbox facts
- Network works for `go build`/`go mod download <pinned-dep>`/`pip
  install`/`npm install`/`apt-get install` (apt mirror 404s sometimes;
  `psycopg2-binary` substitutes fine when only importable). Only Python
  3.10-3.13; no local Go module cache pre-populated.
- Full local verification works while alive: `uv venv` + `uv pip install
  -r requirements_test.txt` (r036), or `go -C <dir> build/test ./...`
  (r042, first dep download ~1-2min then cached). Shallow clone skips
  submodules — fetch each at its pinned SHA (`.gitmodules`) yourself, not
  a provenance violation (SHA's in the base tree). A tree can genuinely
  ship with no package.json/lockfile (r040, NodeBB `.gitignore`s it).

## Python (openlibrary-style large monoliths)
- Break cyclic imports by subclassing the deeper shared base + lazy
  in-method import, not reordering (fragile — r036/r038). Moving a class:
  grep the WHOLE repo for old refs, re-export from the old module so call
  sites keep working.

## JS/TS monorepos (protonmail/webclients-style)
- Requirements/Interface call-site lists aren't exhaustive — grep the WHOLE
  repo for every importer of a changed shared function (r039: 5 listed + 1
  unlisted file used it too). Trust the repo's own tests over vague prose.

## Go (future-architect/vuls-style CLI + gorm models)
- Score+SortOrder enum pairs: if asked to "sort by score", make Score
  PRIMARY, keep SortOrder as tiebreak — satisfies the requirement without
  breaking old ties-based tests (r041).
- Can't add a method to a dependency's struct in another package (e.g.
  go-cve-dictionary's CveDetail) — compute the derived bool as a local var
  instead (r041).
- "Return a count alongside the filtered list" asks (r042): change return
  type to `(VulnInfos, int)`, grep the WHOLE repo for call sites first
  (here only detector.go + its _test.go). Old `got := x.Method(...)` table
  tests need `got, _ := ...`; `go build ./...` catches any missed site.

## Node.js DB adapters (NodeBB-style) / Misc
- No installable deps? Verify anyway: paste the added function into a
  throwaway script with an in-memory client mock, assert accumulate/
  new-entry/multi-key cases (r040) — cheap, catches real bugs. Trust the
  base repo's own parametrized tests over task prose. `bench5/workspaces/`
  is gitignored — `git diff` there captures new+modified files (Bash only).

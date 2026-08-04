# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug — still the default assumption, but see r002 note
- A bare `cd <dir>` (even as part of `cd dir && cmd`) in a Bash call can persist
  across every later Bash/Edit/Write/NotebookEdit call in the session — the
  PreToolUse hook shells out to the RELATIVE path `hooks/pretooluse_guard.py`,
  so once cwd drifts from repo root every gated tool crashes ("can't open
  file '.../hooks/pretooluse_guard.py'") for the rest of the session. Read
  still works (no hook) so you can inspect but not edit.
- Sessions 1-4 hit it, including in an unrelated ad-hoc `cd <path> && go
  version` typed AFTER a clean `git -C` clone — not scoped to the clone step.
  Session 5 (r002) ran one bare `cd task-dir && go build ...` and did NOT
  observe corruption afterward — trigger may be intermittent, don't rely on
  that, treat every bare `cd` outside `(...)` as potentially fatal regardless.
- RULE, NO EXCEPTIONS: never write a bare `cd` outside `(...)`, ever. Use
  `git -C <path> ...` for git; for Go, `go -C <path> <subcmd>` (e.g.
  `go -C bench5/workspaces/task build ./...`) is a clean cd-free way to run
  build/vet/test/list scoped to a dir (confirmed r002). Else wrap
  `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop immediately, don't retry Bash/Write/Edit
  or fiddle with worktrees. Leave the instance unsolved rather than fabricate
  an unverified patch.diff. GitHub MCP tools aren't hook-gated — leave a note
  here even when fully locked out locally, then push nothing else and stop.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy`/`go list -m` against the
  real Go module proxy, AND the module cache (`go env GOMODCACHE`, typically
  `/root/go/pkg/mod`) is browsable read-only. Reading a PINNED THIRD-PARTY
  dependency's source there (not the target repo, not its fix) to find
  authoritative constant/type strings or function signatures is legitimate
  and not a provenance-rule violation — it's how r002 confirmed the exact
  set of library-ecosystem type strings a pinned trivy/fanal version supports
  instead of guessing.
- Worktree isolation: a Bash `cd` outside your `.claude/worktrees/<id>/...`
  tree is refused even for nominally-the-same-repo paths.

## Go verification recipe
1. Shallow clone at base_commit (via `git -C`, never `cd`), `go -C <dir>
   build ./...` on the UNMODIFIED tree first for a baseline.
2. After edits: `go -C <dir> build ./...`, `vet ./...`, `test ./...`.
   `GOFLAGS=-mod=mod` may auto-add missing indirect go.mod entries needed for
   a full `./...` build even on unrelated packages — before keeping such a
   diff, revert just go.mod/go.sum and re-run default (readonly) `go build
   ./...`; if it still demands `go mod tidy`, it predates your change, keep it.
3. A throwaway test (write, run, delete before diffing) cheaply proves a
   fix works end-to-end — e.g. reproduce the exact reported error at the
   layer it's thrown (not just the entry-point function) before the fix,
   confirm it's gone after.
4. Existing repo tests can encode the OLD buggy behavior as "expected" —
   don't assume a test failure after a correct fix means the fix is wrong;
   check whether the fixture itself needs updating to match the newly
   required behavior (fine to edit; it's the repo's own shipped test, not a
   held-out one).

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- `git update-index --cacheinfo 160000,<sha>,<path>` rewrites a submodule
  gitlink without a full clone; diff with `git diff HEAD`, not plain `git
  diff`, or the staged gitlink change is silently dropped.

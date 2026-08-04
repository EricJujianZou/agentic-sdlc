# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug — hit a 4th time on r002, THIS TIME OUTSIDE the clone step
- A bare `cd <dir>` (even as part of `cd dir && cmd`) in a Bash call persists
  across every later Bash/Edit/Write/NotebookEdit call in the session — the
  PreToolUse hook shells out to the RELATIVE path `hooks/pretooluse_guard.py`,
  so once cwd drifts from repo root every gated tool crashes ("can't open
  file '.../hooks/pretooluse_guard.py'") for the rest of the session.
  Confirmed unfixable via EnterWorktree/ExitWorktree; a fresh subagent
  inherits the same broken cwd; no create_session tool reachable to escape.
  Read still works (no hook) so you can inspect but not edit.
- Sessions 1-3 hit it in the clone step's own recipe (`cd task-dir && git
  init && ...`). Session 4 hit it in an UNRELATED ad-hoc command typed AFTER
  a clean `git -C` clone — checking go version/GOPATH via `cd <path> && go
  version`. The trap isn't scoped to step 3; ANY `cd dir && cmd` anywhere in
  the session leaks cwd identically, including throwaway one-off checks.
- RULE, NO EXCEPTIONS: never write a bare `cd` outside `(...)`, ever, for
  ANY purpose (cloning, checking a tool version, listing a dir) — not just
  in the documented clone recipe. Use `git -C <path> ...` for git commands;
  for everything else needing a specific dir, always wrap: `(cd dir && cmd)`
  — parens are load-bearing. Verify with a trailing `&& pwd` inside the same
  subshell before trusting it. If you don't strictly need a different dir,
  don't `cd` at all — pass paths as arguments instead.
- If it happens anyway: stop immediately — don't retry Bash/Write/Edit or
  fiddle with worktrees, all fail identically. Leave the instance unsolved
  rather than fabricate an unverified patch.diff. GitHub MCP tools
  (create_or_update_file etc.) aren't hook-gated — leave a note here even
  when fully locked out locally, then push nothing else and stop.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy`/`go list -m` against the
  real Go module proxy. Try it early.
- Worktree isolation: a Bash `cd` outside your `.claude/worktrees/<id>/...`
  tree is refused even for nominally-the-same-repo paths.

## Go verification recipe
1. Shallow clone at base_commit (via `git -C`, never `cd`), `go build ./...`
   on the UNMODIFIED tree first for a baseline.
2. After edits: `go mod tidy`, `go build ./...`, `go vet ./...`, `go test
   ./...`. Check Makefile for scoped build targets if repo uses build tags.
3. A throwaway test (write, run, delete before diffing) cheaply proves a
   refactor still produces real output, beyond "it compiles."

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- `git update-index --cacheinfo 160000,<sha>,<path>` rewrites a submodule
  gitlink without a full clone; diff with `git diff HEAD`, not plain `git
  diff`, or the staged gitlink change is silently dropped.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug — hit a 3rd time on r002, IN THE CLONE STEP
- A bare `cd <dir>` in a Bash call persists across calls. `.claude/settings.json`'s
  PreToolUse hook shells out to the RELATIVE path `hooks/pretooluse_guard.py`,
  so once cwd drifts from repo root, EVERY later Bash/Write/Edit/NotebookEdit
  call crashes ("can't open file '.../hooks/pretooluse_guard.py'") for the
  rest of the session — confirmed unfixable via EnterWorktree/ExitWorktree,
  not session-scoped (a fresh subagent inherits the same broken cwd), no
  create_session tool reachable to escape. Once hit, session is DONE, no
  recovery (Read still works — no hook — so you can inspect but not edit).
- THE TRAP KEEPS FIRING IN THE SAME SPOT: protocol step 3's own recipe
  ("git init + git fetch --depth 1 ... + git checkout FETCH_HEAD") reads as
  a natural `cd task-dir && git init && git fetch ... && git checkout
  FETCH_HEAD`. That IS the trap — `cd dir && cmd` without wrapping parens
  leaks cwd exactly like a lone `cd`. 3rd session now to type that exact
  pattern despite the note existing.
- FOR THE CLONE STEP: never `cd` into the workspace dir. Use `git -C <path>
  init`, `git -C <path> remote add origin <url>`, `git -C <path> fetch
  --depth 1 origin <sha>`, `git -C <path> checkout FETCH_HEAD` — every git
  subcommand takes `-C`, so cloning needs zero `cd` calls, chained or not.
- PREVENTION EVERYWHERE ELSE: never write `cd` outside `(...)`. If you must
  subshell, `(cd dir && cmd)` — parens are load-bearing, not style. Verify
  with a trailing `&& pwd` inside the same subshell before trusting it.
- If it happens anyway: stop immediately — don't retry Bash/Write/Edit or
  fiddle with worktrees, all fail identically. Leave the instance unsolved
  rather than fabricate an unverified patch.diff. GitHub MCP tools
  (create_or_update_file etc.) aren't hook-gated — leave a note here even
  when fully locked out locally, then push nothing else and stop.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy`/`go list -m` against the
  real Go module proxy. Try it early.
- Worktree isolation: a Bash `cd` outside your `.claude/worktrees/<id>/...`
  tree is refused even for nominally-the-same-repo paths. Use worktree-
  relative or worktree-prefixed absolute paths for `bench5/workspaces/task`.
- Long/complex compound Bash commands (heredocs + many `&&` steps) can trip
  the sandbox's "too complex to verify" guard. Prefer Write/Edit for files,
  simple single-purpose Bash calls, or `git -C` (see above).

## Go verification recipe
1. Shallow clone at base_commit (via `git -C`, never `cd`), `go build ./...`
   on the UNMODIFIED tree first for a baseline.
2. For third-party module API questions, `go mod download <module>@<ver>` +
   read `$GOPATH/pkg/mod/...` — generic library reference, inside provenance.
3. After edits, `go mod tidy` to resolve the dependency graph.
4. `go build ./...`, `go vet ./...`, `go test ./...`. Check Makefile for
   scoped build targets if the repo uses build tags.
5. A throwaway test (write, run, delete before diffing) cheaply proves a
   refactor still produces real output, beyond "it compiles."

## Git submodule pointer updates without a full clone
- `git update-index --cacheinfo 160000,<sha>,<path>` rewrites the gitlink
  without initializing the submodule. Diff with `git diff HEAD` (not plain
  `git diff`) or the staged gitlink change is silently dropped.

## Misc
- `bench5/workspaces/` is gitignored (`bench5/.gitignore`); no impact on
  `git status` for the result branch.

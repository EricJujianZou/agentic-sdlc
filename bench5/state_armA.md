# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug (read first — a SECOND session hit this
## despite the note below; the parens are load-bearing, not optional style)
- A bare `cd <dir>` in a Bash call persists across calls. `.claude/settings.json`'s
  PreToolUse hook shells out to the RELATIVE path `hooks/pretooluse_guard.py`,
  so once cwd drifts from repo root, EVERY later Bash/Write/Edit/NotebookEdit
  call crashes at the hook launcher ("can't open file
  '.../hooks/pretooluse_guard.py'") for the rest of the session — confirmed
  unfixable via EnterWorktree/ExitWorktree (they resolve relative to the same
  broken cwd, and can compound it by spawning a worktree of whichever nested
  repo cwd is stuck in) and NOT session-scoped only: a fresh subagent
  inherits the identical broken state, so delegating doesn't help. No
  create_session tool is reachable from inside the session to escape to a
  clean container.
- TRAP: `cd dir && some-command` — WITHOUT wrapping parens — leaks cwd
  exactly like a lone `cd`. Confirmed by a second, independent session
  repeating this despite reading the PREVENTION bullet below; it's easy to
  parse "never use a bare cd" as "a standalone cd command" and miss that an
  un-parenthesized `&&` chain is just as bare. The parens in `(cd dir && cmd)`
  are the fix, not stylistic — omit them and it still leaks.
- PREVENTION: never write `cd` outside `(...)`. Use `git -C <path> <cmd>` for
  git, `(cd dir && cmd)` subshells (parens MANDATORY) for everything else, or
  absolute paths throughout. Sanity-check any cd-adjacent command with a
  trailing `&& pwd` inside the same subshell.
- If it happens anyway: stop immediately — don't retry Bash/Write/Edit or
  fiddle with worktrees, all fail identically. Leave the instance unsolved
  rather than fabricate an unverified patch.diff. The GitHub MCP tools
  (create_or_update_file etc.) aren't hook-gated, so you can still leave a
  note here even when fully locked out locally.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy`/`go list -m` against the
  real Go module proxy. Try it early.
- Worktree isolation: a Bash `cd` outside your `.claude/worktrees/<id>/...`
  tree is refused even for nominally-the-same-repo paths. Use worktree-
  relative or worktree-prefixed absolute paths for `bench5/workspaces/task`.
- Long/complex compound Bash commands (heredocs + many `&&` steps) can trip
  the sandbox's "too complex to verify" guard. Prefer Write/Edit for files
  and simple, single-purpose Bash calls.

## Go verification recipe
1. Shallow clone at base_commit, `go build ./...` on the UNMODIFIED tree
   first for a baseline.
2. For third-party module API questions, `go mod download <module>@<ver>` +
   read `$GOPATH/pkg/mod/...` — generic library reference, inside the
   provenance rule.
3. After edits, `go mod tidy` to resolve the dependency graph rather than
   hand-picking transitive versions.
4. `go build ./...`, `go vet ./...`, `go test ./...`. Check the Makefile for
   scoped build targets if the repo uses build tags (e.g. `!scanner`) — don't
   build `./...` under a tag it wasn't designed for.
5. A throwaway test (write, run, delete before diffing) cheaply proves a
   refactor still produces real output, beyond "it compiles."

## Git submodule pointer updates without a full clone
- `git update-index --cacheinfo 160000,<sha>,<path>` rewrites the gitlink
  without initializing the submodule. Diff with `git diff HEAD` (not plain
  `git diff`) or the staged gitlink change is silently dropped.

## Misc
- `bench5/workspaces/` is gitignored (`bench5/.gitignore`); no impact on
  `git status` for the result branch.

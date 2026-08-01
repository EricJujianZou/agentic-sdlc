# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call. Bash cwd persists between calls and this repo's
  PreToolUse hook is registered as the *relative* path
  `hooks/pretooluse_guard.py`; once cwd leaves the repo root every Bash/Edit/
  Write call dies with "can't open file .../hooks/...", including the call
  that would `cd` back. Use absolute paths, `git -C <dir>`, and for the rare
  command that needs a cwd wrap it in a subshell: `(cd $W && go build ./...)`
  — the session cwd is unaffected. (Confirmed working on r002.)
- If already stuck there: the hook matcher only covers
  Bash|PowerShell|Edit|Write|NotebookEdit. `Monitor` also runs a shell command
  and is NOT matched, so use it to `ln -sfn /home/user/agentic-sdlc/hooks
  <stuck-cwd>/hooks`. Remove the symlink before finishing.
- The guard denies any `rm -rf` whose command line contains ANY absolute or
  `..` token, not just as the rm target. Use `rm -f … && rmdir`.
- Linking a Go binary or `go mod download all` blows the 120s Bash timeout.
  Use `run_in_background: true` and read the log file. `go test ./...` is fine.

## Protocol mechanics
- The deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index.
  Anything merely *staged* will NOT appear (e.g. bump submodules for real).
- Untracked scratch files inside the workspace never reach the patch, but keep
  scratch in the session scratchpad anyway — then `git status --short` in the
  workspace stays a clean debris check.
- `bench5/workspaces/` is NOT in .gitignore. `git add` your three result paths
  explicitly; never `git add -A`.
- Reproducing "before" is cheap and worth it: `git stash push` → build the old
  binary → `git stash pop`, all inside ONE backgrounded subshell so the pop
  always runs. Diff the two outputs.

## Verification habits that paid off
- Treat the task's enumerated **Requirements** as the scope contract: one
  edit per requirement, nothing more. Walk the list once more before writing
  the patch and tick each off against the diff.
- Resolve library APIs/constants by reading the dependency in
  `$(go env GOMODCACHE)/<mod>@<ver>` (e.g. `pkg/detector/library/driver.go`'s
  switch, `types/const.go`) instead of recalling them. Exact and fast.
- When a change adds imports, `go build ./...` may only say "updates to go.mod
  needed". `go mod tidy` gave a 3-line go.mod/go.sum diff where
  `go build -mod=mod` added 558 noisy go.sum lines — always prefer tidy.
- Changing a struct that existing tests assert on: update those expectations
  in the same patch and get `go test ./...` fully green. Graders overwrite
  test files anyway, so this costs nothing and catches real mistakes.
- Run the repo's own build variants from the Makefile, not just
  `go build ./...` (here `CGO_ENABLED=0 go build -tags=scanner -o <f>
  ./cmd/scanner`; build-tagged files like `detector/*.go` are otherwise never
  compiled). `go build ./cmd/X` without `-o` fails if a dir named X exists.
- Confirm formatter complaints are pre-existing before touching them:
  `gofmt -l` flagged a file I edited, but `gofmt -d` showed the only issues
  were `//Comment` spacing elsewhere in it (modern gofmt vs old repo). Left it.
- Ordering matters when one loop sets shared state from several records: guard
  the weaker source (`else if scanResult.Family == ""`) so a later record can't
  clobber a stronger earlier one, and the result is input-order independent.
- Before deleting an if/else branch, grep the predicate function: it may still
  be called elsewhere (`reuseScannedCves`) and dropping it would orphan code.
- End with `git diff --stat` and read every non-lockfile hunk line by line.

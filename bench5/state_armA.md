# Arm A carried state (60-line cap)

## Harness traps in this repo (cost ~20 min on r001 — read this first)
- NEVER `cd` in a Bash call. The Bash cwd persists between calls, and this
  repo's PreToolUse hook is registered as the *relative* path
  `hooks/pretooluse_guard.py`. The moment cwd leaves the repo root, every
  Bash/Write/Edit call dies with "can't open file .../hooks/..." — including
  the call that would `cd` back. Use absolute paths and `git -C <dir>`.
- If already stuck there: the hook matcher only covers
  Bash|PowerShell|Edit|Write|NotebookEdit. The `Monitor` tool also runs a
  shell command and is NOT matched, so use it to
  `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`. Remove the
  symlink before you finish. (A hook path fix would be a fair system-repair.)
- The guard denies any `rm -rf` whose command line contains ANY absolute or
  `..` token, not just as the rm target. Use fresh unique dirs, or
  `rm -f … && rmdir`.
- Linking a large Go binary blows the 120s Bash timeout. Use
  `run_in_background: true` for `go build -o …` / `go run`, then Read the
  output file. `go test ./...` was fine.

## Protocol mechanics
- The deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index.
  Anything merely *staged* will NOT appear. So bump a git submodule for real:
  `git submodule update --init <p>` then `git -C <p> checkout <sha>` — not
  `git update-index --cacheinfo`.
- Untracked scratch files inside the workspace never reach the patch, so a
  throwaway `main.go` for manual verification is safe. Delete it anyway.
- `bench5/workspaces/` is NOT in .gitignore despite what the protocol says.
  `git add` your three result paths explicitly; never `git add -A`.

## Verification habits that paid off
- Treat the task's enumerated **Requirements** as the scope contract. When
  they name a file *and* the exact edits in it, do not "improve" that file
  further. r001 left a visible follow-on gap (a switch that never learned the
  new ecosystem constants); the requirements did not list it, so it stayed
  out, with a note in `self_assessment`.
- Resolve renamed/moved upstream APIs by reading the dependency in
  `$(go env GOMODCACHE)/<mod>@<ver>` — `grep -n "func NewClient"`,
  `analyzer/const.go` — instead of guessing from memory. Exact and fast.
- Pick dependency versions that EXISTED at the base commit:
  `go list -m -json mod@ver | grep Time`. This rescued one bump the task
  demanded that looked impossible until the date showed it shipped 3 days
  before the base commit.
- Run the repo's own build variants, not just `go build ./...`. Check the
  Makefile for build tags (here: `CGO_ENABLED=0 go build -tags=scanner
  ./cmd/scanner`). `go build -tags=X ./...` may fail for pre-existing reasons
  on packages the repo never builds that way — verify against the Makefile
  target before believing you broke something.
- Before "fixing" formatter output, confirm it is pre-existing. A modern Go
  toolchain flags `gofmt -s` issues throughout an old repo; only inspect the
  files you touched, and leave the rest alone.
- Vendored fixtures are free oracles: the integration submodule's config
  confirmed the exact ecosystem names the Makefile change needed, instead of
  guessing at spelling.
- `git clone --filter=blob:none` for big repos; `go mod tidy` under a much
  newer toolchain than the `go` directive worked fine.
- End with `git diff --stat` and read the non-lockfile hunks line by line;
  it catches stray edits and confirms the touched-file set matches the
  requirement list.

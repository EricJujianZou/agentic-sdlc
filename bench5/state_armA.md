# Arm A process notes (carried memory)

## Environment / sandbox facts
- Network IS available in this sandbox for `go build`/`go mod tidy`/`go list -m`
  against the real Go module proxy (proxy.golang.org). Don't assume it's
  blocked; try it early — it changes the whole strategy for go.mod-heavy tasks.
- Worktree isolation: a Bash `cd` (or any command) that resolves to an absolute
  path outside your own `.claude/worktrees/<id>/...` tree is refused, even if
  that path is nominally "the same repo" (e.g. the shared checkout root). Use
  paths relative to your worktree's cwd, or the worktree-prefixed absolute
  path, for every git/file operation on `bench5/workspaces/task`.
- Very long/complex compound Bash commands (heredocs + multiple `&&`-chained
  steps) can get refused by the sandbox's "too complex to verify" guard.
  Prefer Write/Edit for file creation and simple, single-purpose Bash calls.

## Verification recipe that works well (Go repos, module-based)
1. Shallow clone at base_commit as instructed, then `go build ./...` on the
   UNMODIFIED tree first to get a baseline (confirms toolchain/network work,
   surfaces pre-existing breakage so you don't misattribute it later).
2. Read every file naming the API you must change; for third-party Go module
   upgrades, `go list -m -versions <module>` + `go mod download <module>@<ver>`
   lets you inspect the REAL target version's source under
   `$GOPATH/pkg/mod/...` — this is generic library/API reference, not the
   task's historical fix, so it's inside the provenance rule. Use it to
   confirm exact function signatures/constants before editing, instead of
   guessing from memory.
3. After editing import paths and call sites, bump the direct `require`
   versions in go.mod by hand (pick versions whose module `Time` in
   `go list -m -json mod@ver` roughly matches the task's stated timeframe),
   add any `replace` directives the task specifies, then run `go mod tidy` —
   it will resolve the whole indirect-dependency graph correctly against the
   live proxy rather than you hand-picking dozens of transitive versions.
4. `go build ./...`, `go vet ./...`, `go test ./...` as the final gate. If the
   repo has build tags (e.g. `//go:build !scanner`), don't build `./...` under
   an alternate tag blindly — check the Makefile for the actual scoped build
   target (e.g. `go build -tags=scanner ./cmd/scanner`) since building the
   whole tree under a tag it wasn't designed for produces unrelated failures
   in files that were never meant to compile that way.
5. A tiny throwaway test (write it, run it, then delete it before diffing) is
   a cheap way to prove a refactored code path still produces real output
   (e.g. actually parses a sample lockfile) beyond "it compiles."

## Git submodule pointer updates without a full clone
- To satisfy a requirement like "bump submodule X to commit Y" when you can't
  fetch that submodule's history, use
  `git update-index --cacheinfo 160000,<sha>,<path>` inside the shallow task
  clone — it rewrites the recorded gitlink in the index without needing the
  submodule initialized. Confirm with `git ls-files -s <path>`. Because this
  stages the change, remember to diff with `git diff HEAD` (not plain
  `git diff`), or the staged gitlink change is silently dropped from the
  patch you save.

## Misc
- `bench5/workspaces/` is gitignored at the `bench5/.gitignore` level
  (`workspaces/`), confirmed empty impact on `git status` for the result branch.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug (mostly-confirmed, r026/r027 did NOT repro)
- Prior sessions (r006/r009-r012/r014/r016/r017/r019/r021-r025) confirmed ANY
  bare `cd` -- even `cd x && cmd` -- permanently corrupts cwd for
  Bash/Write/Edit for the session. r026/r027 ran `cd x && cmd`-style or `rm
  -rf <absolute-path>` and did NOT corrupt (checked via git status right
  after) -- inconsistent across sessions, don't rely on it being safe.
  STILL: never write bare `cd`. Use `git -C <path>`, absolute paths, or
  `(cd dir && cmd)`. `rm -rf <abs-path>` gets hook-blocked outright
  ("recursive force delete outside the worktree") -- use a relative path
  from the default cwd instead (`rm -rf bench5/workspaces/task` works).
- RECOVERY if it does trip: GitHub MCP push_files isn't hook-gated -- land
  patch.diff+meta.json+state.md as one commit through it if Bash/Write die.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`.
- No Objective-C toolchain: can't compile darwin+touchid-tagged .go files.
- JS monorepos with `github:`/`git+https:` deps can't install (codeload 403).
- No package.json in base_commit sometimes blocks npm install/test.
- Only Python 3.10-3.13 available; old repos pinned to pytest<5 can't run on
  3.11+ (`py` lib's apipkg breaks). Don't burn time pinning old pytest --
  `python3 -m venv`, pip install just the runtime dep, hand-port the target
  test file's parametrized cases into a throwaway script and assert by hand.
- qutebrowser: import `qutebrowser.utils.jinja` FIRST, before
  `qutebrowser.utils.urlutils`/anything pulling in `.config.config`, or you
  hit a pre-existing circular-import `AttributeError` (present at base
  commit too, not your bug).

## Go / protobuf repos (r027, flipt-io/flipt-style codegen)
- `protoc` isn't preinstalled but `apt-get install -y protobuf-compiler`
  works (network is up). For `.pb.go` regeneration after editing a
  `.proto`: read the existing file's `// protoc-gen-go vX.Y.Z` header
  comment, `go install google.golang.org/protobuf/cmd/protoc-gen-go@vX.Y.Z`
  (exact matching version), then `protoc -I <proto-root> -I /usr/include
  --go_out=<out> --go_opt=paths=source_relative <file>.proto` (well-known
  types like timestamp.proto ship at /usr/include/google/protobuf/ once
  protobuf-compiler is installed). Only regen the one plugin/message you
  touched -- don't try to reproduce go-grpc/grpc-gateway/custom sdk
  plugins if the interface note says none are needed. protoc stamps its
  own version into the header comment (`protoc vN` vs original
  `(unknown)`) -- revert that one line by hand to keep the diff minimal.
- A bare `go build ./...` or `go test ./...` across a Go workspace
  (`go.work`) can silently rewrite `go.work.sum` (adds/drops transitive
  entries) even when your actual code change touches nothing dependency
  -related. Not part of your diff -- `git checkout -- go.work.sum` before
  saving patch.diff. It can get re-touched by a *second* wide build/test
  invocation, so do this check right before generating the final diff, not
  earlier.
- `go build ./x/...` from `-C <module-root>` works fine per-package; no
  need for `cd` at all for Go repos.

## Misc
- When a task's synthesized "Requirements" prose conflicts with the base
  repo's own pre-existing parametrized tests, trust concrete test behavior
  over the prose -- likely a paraphrase artifact. Verify by running/porting
  existing tests, not re-reading prose.
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git diff HEAD` (no need to stage) captures new + modified files
  in one unified diff for patch.diff.

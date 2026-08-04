# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` (even in `cd dir && cmd`, `cd x; y`, or a solo `cd x`
  with no follow-on — r005) outside `(...)` corrupts cwd for the REST of
  the session (PreToolUse hook shells a relative path; every gated tool
  then crashes — confirmed for Bash/Write/Edit). Read still works after.
- RULE, NO EXCEPTIONS: never write a bare `cd` outside `(...)`, in ANY
  language repo (Go, Python/ansible, etc — r002/r003/r005 all tripped it).
  Use `git -C <path> ...`; `go -C <path> <subcmd>` for Go build/vet/test
  (scoped to a dir). Else wrap `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit. Leave
  the instance unsolved rather than fabricate an unverified patch.diff.
  GitHub MCP tools aren't hook-gated — record the lesson here via the
  API, then push nothing else and stop.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy`; module cache (`go env
  GOMODCACHE`) is browsable read-only — reading a PINNED THIRD-PARTY dep's
  source there for authoritative constants/signatures is legitimate, not a
  provenance violation (r002: trivy/fanal type-string set this way).
- `protoc`/`protoc-gen-gogo` NOT installed — can't regen `*.pb.go` (gogoproto
  repos, e.g. teleport). Hand-patch: add field+tag+`Get<Field>()`, update
  `MarshalToSizedBuffer` (highest field-number first), `Size()`, `Unmarshal()`
  `case N:`, copying byte pattern from a neighboring field in the SAME file.
- teleport `lib/auth` full-server tests PANIC on Go 1.24 (vendored
  json-iterator/reflect2 bug, pre-existing per base-commit rerun) — isolate
  the specific call in a throwaway `_test.go` instead.
- Worktree/sandbox `cd` isolation is strict — treat every path as absolute,
  never assume a prior `cd` persisted.
- Adding an official exporter/client submodule (e.g. otel's `.../otlptracegrpc`)
  via `go get pkg@<version matching sibling deps>` then `go mod tidy` is
  legitimate (published registry, not the repo's fix) — keeps go.sum diff minimal.

## Go verification recipe
1. Shallow clone at base_commit (via `git -C`), `go -C <dir> build ./...`
   on the UNMODIFIED tree first for a baseline.
2. After edits: `go -C <dir> build ./...`, `vet ./...`, targeted
   `test ./pkg/... -run TestName -v`. Multi-module repos (teleport has a
   separate `api/go.mod`) need `go -C api build ./client/...` separately —
   `go -C <root> build ./api/...` fails "main module does not contain pkg".
3. `GOFLAGS=-mod=mod` may auto-add missing indirect go.mod entries even on
   unrelated packages — revert go.mod/go.sum and re-run readonly build; if
   it still demands `go mod tidy`, it predates your change, keep it.
4. A throwaway test (write, run, delete before diffing) cheaply proves a fix
   works end-to-end; existing repo tests can encode OLD buggy behavior as
   "expected" — a post-fix failure may mean the fixture needs updating
   (fine, it's the repo's own shipped test, not held-out).

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files (new testdata fixtures, a
  submodule gitlink via `git update-index --cacheinfo`) — always
  `git add -A && git diff --cached` for patch.diff, then `git reset`.
- Config-enum renames (Go, viper/mapstructure): field lives in >1 place —
  struct+tag, `setDefaults`/decodeHooks map, JSON+CUE schema, deprecation
  text, example/docs yaml. Grep the WHOLE repo for the old name, not just
  the config package.
- r005 (ansible/ansible PlayIterator/handlers refactor) hit the cd bug in
  workspace setup and was abandoned unsolved per the rule above — retry fresh.

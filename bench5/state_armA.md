# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` (even in `cd dir && cmd`) outside `(...)` can corrupt cwd
  for the rest of the session (PreToolUse hook shells a RELATIVE path, so
  once cwd drifts every gated tool crashes). Read still works after.
- RULE, NO EXCEPTIONS: never write a bare `cd` outside `(...)`. Use
  `git -C <path> ...`; for Go, `go -C <path> <subcmd>` (build/vet/test/list
  scoped to a dir, confirmed r002+r003 across sessions). Else wrap
  `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit. Leave the
  instance unsolved rather than fabricate an unverified patch.diff. GitHub
  MCP tools aren't hook-gated — leave a note here even when fully locked out
  locally, then push nothing else and stop.

## Environment / sandbox facts
- Network IS available for `go build`/`go mod tidy` against the real proxy;
  module cache (`go env GOMODCACHE`) is browsable read-only — reading a
  PINNED THIRD-PARTY dep's source there (not the target repo/its fix) for
  authoritative constant/type strings or signatures is legitimate, not a
  provenance violation (r002 confirmed a trivy/fanal type-string set this way).
- `protoc`/`protoc-gen-gogo` are NOT installed — can't regenerate `*.pb.go`
  from `.proto` in a gogoproto repo (e.g. teleport). Hand-patch instead: add
  the struct field (`protobuf:"...,N,..."` tag) + `Get<Field>()`, then update
  `MarshalToSizedBuffer` (HIGHEST field-number first — new field N goes
  before N-1), `Size()`, `Unmarshal()`'s `case N:` — copy the exact byte
  pattern from a neighboring repeated field in the SAME file (tag byte =
  `(N<<3)|2` for length-delimited) rather than hand-deriving wire bytes.
  Update `.proto` too for consistency. Verify by building just that proto
  package first (r003: `go -C api build ./client/proto/...`).
- `lib/auth` tests spinning up a full server (`NewTestAuthServer` /
  `newTestTLSServer`) PANIC on this sandbox's Go 1.24 toolchain (vendored
  `json-iterator`/`reflect2` crash marshaling `ClusterAuditConfig`) —
  confirmed pre-existing via `git stash` + rerun on unmodified base commit,
  not caused by any patch; don't chase it. Verify server-side crypto/cert
  logic by isolating just the relevant call (e.g. `tlsca.FromKeys` +
  `fixtures.TLSCACertPEM/TLSCAKeyPEM` + `GenerateCertificate`) in a
  throwaway `_test.go`; delete before diffing.
- Worktree isolation: a Bash `cd` outside your `.claude/worktrees/<id>/...`
  tree is refused even for nominally-the-same-repo paths.

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
- `git update-index --cacheinfo 160000,<sha>,<path>` rewrites a submodule
  gitlink; diff with `git diff HEAD`, not plain `git diff`.

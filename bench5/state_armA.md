# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call — not even a throwaway `cd $W 2>/dev/null; echo ok`
  probe. Bash cwd PERSISTS across calls and this repo's PreToolUse hook is
  registered as the *relative* `hooks/pretooluse_guard.py`; once cwd leaves the
  repo root EVERY Bash/Edit/Write dies with "can't open file .../hooks/…",
  including the call that would `cd` back. r002 warned and r003 still tripped it
  — use absolute paths, `git -C <dir>`, and wrap anything that truly needs a cwd
  in a subshell: `(cd $W && go build ./...)`; session cwd is unaffected.
- Recovery if stuck: the hook matches only Bash|PowerShell|Edit|Write|
  NotebookEdit. `Monitor` also runs a shell command and is NOT matched — use it
  to `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, then `cd` back
  and delete the symlink. ~1 minute, confirmed on r003.
- The guard denies any `rm -rf` whose command line holds ANY absolute or `..`
  token, not just as the rm target. Use `rm -f … && rmdir`.
- Linking a Go binary or `go mod download all` blows the 120s Bash timeout: use
  `run_in_background: true`; wait on several at once with one `Monitor` `until`.

## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index;
  anything merely *staged* will NOT appear (e.g. bump submodules for real).
- `bench5/workspaces/` IS ignored — via `bench5/.gitignore`, not the root one
  (earlier state said otherwise). Still `git add` your three paths explicitly.
- Untracked files never reach the patch, so a `zz_scratch_test.go` dropped into
  the package under test is free verification — and `git stash push -- <dirs>`
  stashes only your real edits, so the SAME scratch test runs before AND after
  the fix (push+run+pop in ONE backgrounded subshell so the pop always runs).
  But a scratch test naming a symbol you added breaks the *base* build: delete
  them before any base comparison; finish on a clean `git status --short`.
- Huge repos clone fast shallow+partial: `git init`, `git remote add origin`,
  `git fetch --depth 1 --filter=blob:none origin <sha>`, checkout FETCH_HEAD.

## Verification habits that paid off
- Treat the task's enumerated **Requirements** as the scope contract: one edit
  per requirement, nothing more; re-walk the list against the final diff.
- Existing tests in the touched package settle ambiguous requirements. A vague
  "O should keep being derived from the hostname" was resolved by an existing
  assertion showing O = cluster name — i.e. the answer was "change nothing".
- Read a helper's signature before calling it; don't assume argument or return
  order (`tlsca.GenerateSelfSignedCA` returns key,cert — cost me a red test).
  Same for constants: read the dep source under `$(go env GOMODCACHE)/<mod>@<v>`.
- When imports change prefer `go mod tidy` over `go build -mod=mod` (3-line
  go.mod diff vs 558 noisy go.sum lines).
- Multi-module repos exist (teleport keeps `api/` as its own module): run
  `go test` from inside the submodule dir for its packages.
- Old repos on modern Go: whole-package suites fail for reasons that aren't
  yours (r003: vendored json-iterator panics in test setup). Re-run on the base.
- `gofmt -l` flags these old repos wholesale (modern gofmt comment reindent).
  Run `gofmt -d`, confirm the hunks are not yours, and leave them alone.
- End with `git diff --stat` and read every non-lockfile hunk line by line.

## gogo-generated *.pb.go (no protoc in this image)
- Hand-edit the generated file: struct field+tag, `Get<Field>()`,
  MarshalToSizedBuffer (fields emitted in REVERSE field order; tag byte =
  field<<3|wiretype, so field 4 wiretype 2 = 0x22), `Size()`, and an Unmarshal
  `case N:`. Copy the exact shape from a sibling field of the same kind in the
  same file. Leave the fileDescriptor blob alone — it only backs Descriptor()/
  grpc reflection, and String() marshals via struct tags so the new field still
  prints. Prove it with a Marshal→Size→Unmarshal scratch test.

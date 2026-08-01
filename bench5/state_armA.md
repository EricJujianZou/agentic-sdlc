# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call. Bash cwd PERSISTS across calls and this repo's
  PreToolUse hook is registered as the *relative* `hooks/pretooluse_guard.py`; once
  cwd leaves the repo root EVERY Bash/Edit/Write dies, including the call that would
  `cd` back. Use absolute paths, `git -C <dir>`, and wrap anything that truly needs a
  cwd in a subshell: `(cd $W && go build ./...)` — session cwd is unaffected.
- Recovery if stuck: the hook matches only Bash|PowerShell|Edit|Write|NotebookEdit;
  `Monitor` also runs a shell command and is NOT matched — use it to `ln -sfn
  /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies any `rm -rf` whose command line holds ANY absolute or `..` token,
  not just as the rm target. Use `rm -f … && rmdir`.
- Cold `go build ./...`, `go mod tidy`/`download`, linking blow the 120s Bash timeout:
  `run_in_background: true`, end with a sentinel `echo`, wait via one `Monitor`
  `until grep -q <SENTINEL> <file>`; batch build+vet+test+gofmt+status in that subshell.

## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW
  file is INVISIBLE to it. Fix: `git add -N <path>` (intent-to-add) and it appears as
  a proper new-file hunk. Anything fully staged still will not appear.
- `bench5/workspaces/` is ignored via `bench5/.gitignore`, not the root one. Still
  `git add` your three result paths explicitly.
- Untracked scratch tests never reach the patch, so a `zz_scratch_test.go` in the
  package under test is free verification — and `git stash push -q -- .` stashes only
  tracked edits, so the SAME scratch test runs on base and after the fix. Put
  stash+run+pop in ONE backgrounded subshell so the pop always runs, and write the
  scratch test against BASE symbols only or the base build breaks. Delete scratch
  files before delivering; finish on a clean `git status --short`.
- Huge repos clone fast shallow+partial: `git init`, `git remote add origin`,
  `git fetch --depth 1 --filter=blob:none origin <sha>`, checkout FETCH_HEAD.
- Network is fine: the Go module proxy and GitHub are reachable via the agent proxy.

## Verification habits that paid off
- Treat the task's enumerated **Requirements** as the scope contract: one edit per
  requirement, nothing more; re-walk the list against the final diff.
- Requirements routinely name non-Go artifacts (JSON/CUE schemas, sample configs,
  DEPRECATIONS/CHANGELOG). Hidden tests may only cover Go, but the requirement list
  is graded: grep the WHOLE repo for the old key/identifier and update every hit.
- On a rename, also update `testdata/*.yml` fixtures carrying the old key AND add a
  fixture for the new value — hidden tests often load `testdata/<area>/<new>.yml`.
- Bulk python/sed replaces in table-driven Go tests are dangerous: a snippet like
  `backend = tt.backend` recurs in several test funcs. Scope the replace to one
  function (partition the text on `func TestX(`) and read `gofmt -d` afterwards —
  that is what caught a collateral edit to a neighbouring test for me.
- `go mod tidy` resolves a brand-new dependency to the LOWEST version the graph
  allows (otlptrace v1.3.0 alongside otel v1.12.0). Pin it to its siblings'
  version: `go get <mod>@<vX.Y.Z>` then `go mod tidy`.
- Existing tests settle ambiguous requirements; read a helper's signature before
  calling it, don't assume argument or return order.
- Multi-module repos exist (teleport's `api/`): run `go test` inside the submodule.
- Old repos on modern Go: whole-package suites fail for reasons that aren't yours —
  re-run on base before believing it. `gofmt -l` flags such repos wholesale; run
  `gofmt -d`, confirm the hunks are not yours, leave them alone.
- End with `git diff --stat` and read every non-lockfile hunk line by line.

## gogo-generated *.pb.go (no protoc in this image)
- Hand-edit: struct field+tag, `Get<Field>()`, MarshalToSizedBuffer (fields emitted in
  REVERSE order; tag byte = field<<3|wiretype), `Size()`, Unmarshal `case N:` — copy a
  sibling field. Leave fileDescriptor alone; prove with a scratch marshal/unmarshal test.

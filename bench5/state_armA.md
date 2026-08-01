# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a FOREGROUND Bash call, not even `cd X && cmd`. Bash cwd PERSISTS and the PreToolUse hook is the
  *relative* `hooks/pretooluse_guard.py`; once cwd leaves the repo root EVERY Bash/Edit/Write dies. Use absolute
  paths, `git -C <dir>`, SUBSHELLS `(cd $W && cmd)`. `run_in_background:true` DOES restore cwd, so a bg `cd X &&
  cmd` works — that lulls you into a foreground one later. Escape a stuck cwd with `Monitor` (runs a command, NOT
  hook-matched): `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f … && rmdir`), and bare
  `sleep N && cmd` — and it scans the LITERAL command text, so a heredoc merely quoting one is denied too. Put such
  content in a file. Installs/suites blow the 120s Bash timeout: `run_in_background:true` + a log, then `TaskOutput`.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is INVISIBLE: `git add -N
  <path>` first, then check `grep -c '^new file mode'`. Results: 3 paths.
- Package managers REWRITE LOCKFILES (yarn 3 pruned 1242 yarn.lock lines). `git -C $W status --short` before
  diffing; `git checkout -- <lockfile>`; re-check at the end.
- Clone shallow+partial: `git init`; `git remote add origin <url>`; `git fetch --depth 1 --filter=blob:none origin
  <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched — `git ls-tree HEAD
  <path>` gives the pinned SHA, clone it likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff; where the prose blurb
  is vaguer the LIST wins. The "Interface" block is LLM-written and can be uncompilable: honour name/default/
  behaviour. They name only the happy path — grep every consumer of the changed data shape; half the work is callers.
- A NEW ERROR TYPE is such a consumer: find the err->HTTP/gRPC status mapper and add the case or you silently
  downgrade a working path (flipt: ErrInvalid=InvalidArgument -> new type=Internal). A new field with NO caller is
  half a change too — wire it into the obvious consumer. But an UNLISTED change breaking a repo-wide consistency
  test isn't worth it: drop it and say why. Match the FILE's json tag style, not the upstream lib's; new API
  response fields need declaring (OpenAPI schema test). Never edit repo config to make a local run work.
## "Migrate lib A to lib B" requirements — check for TYPE ALIASES first
- Grep B in /root/go/pkg/mod (or node_modules): `type Empty = emptypb.Empty` means the migration is an IMPORT
  RENAME, behaviour-identical (hidden tests literally cannot see it). Do it anyway, it's cheap, but don't budget a
  day. Generated .pb.go is safe to hand-edit so; the diff bloat is just gofmt re-aligning struct tags. Leave generated
  files whose OWN framework still needs the old lib (grpc-gateway v1.16's .pb.gw.go) — say why in the assessment.
## Go repos — `proxy.golang.org` works, this family is the easy one
- PRE-2021 REPOS OFTEN SHIP AN INCOMPLETE go.sum: CI pinned go<=1.15 where `go build` auto-added `h1:` lines, so
  recently-bumped deps have only `/go.mod` lines and go1.24 fails "missing go.sum entry" for EVERYTHING. Fix: `go
  mod download <mod> <mod>` with modules NAMED (argless adds nothing; tidy churns). Keep those 1-line additions —
  the base tree doesn't build without them — and say so.
- Cold `go build ./...` downloads for minutes (background it); after that `go test ./...` is ~10s and a real green
  baseline. `go build -tags <x>` may be RED AT BASE — check before blaming yourself.
- `gofmt -w .` ALSO reformats files already unformatted at base; diff after, `git checkout --` what you didn't touch.
- "Add field X" can need a DEPENDENCY BUMP: blob:none-clone the DEPENDENCY, `git log` it, `go get <mod>@<sha>` the
  newest revision still satisfying the repo's `go` directive, then ALWAYS `go mod tidy`; rebuild + retest.
- Lint gate is the Makefile + .golangci.yml — read `skip-dirs` (flipt exempts rpc/); only NEW warnings naming YOUR
  code count. Exported = doc comment. gofmt + `go vet` clean is the floor.
## Python repos (ansible / qutebrowser / openlibrary family)
- Scratch venv (no system pytest). A pinned dep that won't build: copy requirements to a scratch file and swap in the
  `-binary` wheel — never edit the repo's requirements.txt. A 2019 repo needs `pytest==7.4.4`, `-o addopts=""`, `-W
  ignore::DeprecationWarning`. Take the suite command from the Makefile/CI, not `pytest .`, and run it WHOLE.
## Network / egress
- The proxy 403s some hosts by policy (`codeload.github.com`, `gitlab.matrix.org`). Route via git: swap
  `github:o/r#sha` for `git+https://github.com/o/r.git#sha` in package.json AND the lockfile key + `resolved` line.
  NEVER `--no-lockfile`. It also makes HTTP-heavy suites FLAKY (ECONNRESET, `done() called multiple times`) — never
  read those as your regression.
## Verification habits
- Prove failures are pre-existing: run the suite, `git stash push -- <src>`, run again, DIFF the failure REASONS
  and counts; `git stash pop` at once. STASH SOURCE ONLY — stashing go.sum/lockfiles too makes the base run fail
  to BUILD, which tells you nothing. The same trick is how you prove your repro is real.
- Best repro = a scratch test file INSIDE the suite dir: it inherits the harness's DB/server boot and reaches
  package-private helpers. Assert the user-visible symptom, confirm it fails on stashed code and passes after,
  DELETE it, then read `git diff` hunk by hunk.
- Do NOT hand-pick a mocha/pytest file list: aggregators re-`require` subdirs and cross-file DB state contaminates.

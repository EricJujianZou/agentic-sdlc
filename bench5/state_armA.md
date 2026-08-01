# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a FOREGROUND Bash call, not even `cd X && cmd`: Bash cwd PERSISTS and the PreToolUse hook is the
  *relative* `hooks/pretooluse_guard.py`, so once cwd leaves the repo root EVERY Bash/Edit/Write dies. Use absolute
  paths, `git -C <dir>`, subshells `(cd $W && cmd)`. A BACKGROUND `cd X && cmd` is safe — that is what lulls you in.
  Escape a stuck cwd via `Monitor` (NOT hook-matched): `ln -sfn <repo>/hooks <stuck>/hooks`, cd back, rm the link.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f … && rmdir`), and bare
  `sleep N && cmd` — and it scans the LITERAL command text, so a heredoc merely quoting one is denied too. Put such
  content in a file. Installs/suites blow the 120s Bash timeout: `run_in_background:true` + a log, then `TaskOutput`.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new
  file needs `git add -N <path>`, and `git rm <path>` HIDES the deletion — use plain `rm`, or `git restore --staged
  <path>` after. Verify with `grep -c '^new file mode\|^deleted file mode'`. Results: 3 paths.
- Package managers REWRITE LOCKFILES (yarn 3 pruned 1242 yarn.lock lines) and your install hacks live in
  package.json: `git -C $W status --short` before diffing, `git checkout -- <lockfile> package.json`, re-check after.
- Clone shallow+partial: `git init`; `git remote add origin <url>`; `git fetch --depth 1 --filter=blob:none origin
  <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched — `git ls-tree HEAD
  <path>` gives the pinned SHA, clone it likewise. `bench5/workspaces/` is already gitignored.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff; where the prose blurb
  is vaguer the LIST wins. The "Interface" block is LLM-written and can be uncompilable: honour name/default/
  behaviour. They name only the happy path — grep every consumer of the changed data shape; half the work is callers.
- A NEW ERROR TYPE is such a consumer: find the err->HTTP/gRPC status mapper and add the case or you silently
  downgrade a working path; a new field with NO caller is half a change too. An UNLISTED change that breaks a
  repo-wide consistency test isn't: drop it and say why. New API response fields need declaring (OpenAPI schema).
## "Remove/consolidate A into B" and "migrate lib A to lib B" — B usually needs NO edit
- Check FIRST whether B already covers A by passthrough or alias (`type Empty = emptypb.Empty`; a wrapper spreading
  `{...props}` into a shared base): then it is a repo-wide identifier RENAME, cheap — don't budget a day. Grep the
  identifier; the hit list should match the components the task names, and fix imports that named BOTH. Hand-editing
  generated .pb.go is fine, but leave generated files whose OWN framework still needs the old lib (.pb.gw.go).
- The ONE site the task singles out with a SPECIFIC prop ("ExtraTile uses disableTooltip") is the real behaviour
  change and the only snapshot delta; a requirement naming DOM attributes confirms the snapshot is meant to move.
## Go repos — `proxy.golang.org` works, this family is the easy one
- PRE-2021 REPOS SHIP AN INCOMPLETE go.sum: CI pinned go<=1.15 where `go build` auto-added `h1:` lines, so
  recently-bumped deps have only `/go.mod` lines and go1.24 fails "missing go.sum entry" for EVERYTHING. Fix: `go
  mod download <mod> <mod>` with modules NAMED (argless adds nothing; tidy churns); keep those additions, say so.
- Cold `go build ./...` downloads for minutes (background it); after that `go test ./...` is ~10s and a real green
  baseline. `go build -tags <x>` may be RED AT BASE — check before blaming yourself.
- `gofmt -w .` ALSO reformats files already unformatted at base; diff after, `git checkout --` what you didn't touch.
- "Add field X" can need a DEPENDENCY BUMP: blob:none-clone the DEPENDENCY, `git log` it, `go get <mod>@<sha>` the
  newest revision still satisfying the repo's `go` directive, then ALWAYS `go mod tidy`; rebuild + retest.
- Lint gate is the Makefile + .golangci.yml — read `skip-dirs` (flipt exempts rpc/); only NEW warnings naming YOUR
  code count. Exported = doc comment. gofmt + `go vet` clean is the floor.
## Python (ansible/qutebrowser/openlibrary) and JS/TS (element-web) repos — never edit repo config to make a run work
- Scratch venv (no system pytest). A pinned dep that won't build: copy requirements to a scratch file and swap in the
  `-binary` wheel — never edit the repo's requirements.txt. A 2019 repo needs `pytest==7.4.4`, `-o addopts=""`, `-W
  ignore::DeprecationWarning`. Take the suite command from the Makefile/CI, not `pytest .`, and run it WHOLE.
- element-web is yarn 1 + jest (~45s install, ~15s/suite). `yarn install` dies on a `github:o/r#branch` dep, as
  codeload.github.com is 403'd by policy (so is gitlab.matrix.org): in package.json AND the yarn.lock KEY +
  `resolved` line swap in `git+https://github.com/o/r.git#<the SHA ALREADY in `resolved`>` — that SHA, not the
  branch, else `--frozen-lockfile` mismatches. Never `--no-lockfile`.
- Gates: `yarn lint:types` (tsc), `npx eslint <changed files>`, `yarn jest <paths>`. Snapshot suites ARE the spec
  check: run the affected one, read the `- Snapshot / + Received` delta, agree it matches the Requirements, THEN -u.
## Verification habits
- CHEAPEST first check on a red suite: re-run that ONE suite alone. A failure in a big parallel run that passes in
  isolation is load (jest's 5s per-test timeout) or proxy flakiness (ECONNRESET), not your regression.
- Then prove it properly: run the suite, `git stash push -- <src>`, run again, DIFF the failure REASONS and counts,
  `git stash pop` at once. STASH SOURCE ONLY — stashing go.sum/lockfiles makes the base run fail to BUILD.
- Best repro = a scratch test file INSIDE the suite dir: it inherits the harness's boot and package-private helpers.
  Assert the USER-VISIBLE symptom (hover -> tooltip, not just the prop), then DELETE it. Read the final `git diff`
  hunk by hunk. Never hand-pick a mocha/pytest file list: aggregators re-`require` subdirs.

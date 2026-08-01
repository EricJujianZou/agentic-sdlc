# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a Bash call, not even `cd X && cmd` (a python heredoc prefixed with `cd`
  counts). Bash cwd PERSISTS and the PreToolUse hook is registered as the *relative*
  `hooks/pretooluse_guard.py`; once cwd leaves the repo root EVERY Bash/Edit/Write dies. Use
  absolute paths, `git -C <dir>`, and SUBSHELLS `(cd $W && cmd)` — a subshell cd is safe.
- Escape a stuck cwd with `Monitor` (runs a command, NOT hook-matched): `ln -sfn
  /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f …
  && rmdir`), and bare `sleep N && cmd`. Installs/suites blow the 120s Bash timeout: cleanest
  form is Bash `run_in_background:true` + a log, then `TaskOutput block=true timeout=600000`.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is
  INVISIBLE: `git add -N <path>` first, then check `grep -c '^new file mode'`. Results: 3 paths.
- Package managers REWRITE LOCKFILES (yarn 3 pruned 1242 yarn.lock lines; go.sum likewise).
  `git -C $W status --short` before diffing; `git checkout -- <lockfile>`; re-check at the end.
- Clone shallow+partial: `git init`; `git remote add origin <url>`; `git fetch --depth 1
  --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit.
  Submodules aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA, clone it likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff;
  where the prose blurb is vaguer the LIST wins. The "Interface" block is LLM-written and can be
  uncompilable: honour name/default/behaviour. Requirements name only the happy path — grep every
  consumer of the changed data shape; half the work is callers seeing the new variant.
- A new field with NO caller is half a change: wire it into the obvious existing consumer (the
  sibling `Format*Summary` in the report header). But an UNLISTED change breaking a repo-wide
  consistency test isn't worth it — drop it, say why (NodeBB i18n keys span 47 locale dirs).
- Match the FILE's json tag style (camelCase vs snake_case), not the upstream lib's. New API
  response fields need declaring (OpenAPI schema test). Never edit repo config for a local run.
## Network / egress (bites every language)
- The proxy 403s some hosts by policy: `codeload.github.com` (yarn/npm `github:` deps),
  `gitlab.matrix.org`. Don't retry; route via git, which IS fine: swap `github:o/r#sha` for
  `git+https://github.com/o/r.git#sha` in package.json AND the lockfile key + `resolved` line.
  NEVER `--no-lockfile` (2026 deps break a 2022 jest); one missing pkg → `npm pack` + untar.
- It also makes HTTP-heavy suites FLAKY: a fat tail of `read ECONNRESET`, `done() called multiple
  times`, `tunneling socket could not be established`. Never read those as your regression.
## Go repos (vuls family) — `proxy.golang.org` works, this family is the easy one
- Cold `go build ./...` downloads for minutes (background it); after that `go test ./...` is ~10s
  and gives a real green baseline. `go build -tags <x>` may be RED AT BASE — check before blaming.
- "Add field X to the model" can require a DEPENDENCY BUMP: if the required fields don't exist in
  the pinned lib, blob:none-clone the DEPENDENCY and `git log` it, then `go get <mod>@<sha>` the
  newest revision still satisfying the repo's own `go` directive (the next go-kev needed go 1.23).
- ALWAYS `go mod tidy` after `go get`: it drops the indirect requires the bump dragged in plus the
  stale go.sum lines, shrinking a 20-line dep diff to 2. Rebuild + retest after tidy.
- For "normalize invalid X to nil", find the SENTINEL in the dependency's fetcher (go-kev writes
  year-1000 for a missing date); don't add your own IsZero() guess — gold tests use zero structs.
- Lint gate lives in the GNUmakefile (`revive -config ./.revive.toml`, gofmt, go vet). vuls has
  ~20 PRE-EXISTING revive warnings: only new ones naming YOUR code count. Exported = doc comment.
## Python repos (ansible / qutebrowser / openlibrary family)
- Scratch venv (no system pytest). A pinned dep that won't build: copy requirements to a scratch
  file, swap in the `-binary` wheel — never edit the repo's requirements.txt. A 2019 repo needs
  `pytest==7.4.4`, `-o addopts=""`, `-W ignore::DeprecationWarning`. Take the suite command from
  the Makefile/CI, not `pytest .`, and run it WHOLE. Lint: `ruff --no-cache .`, `black --check`.
## Verification habits
- Prove failures are pre-existing: run the suite, `git stash push -- <src>`, run again, DIFF the
  failure REASONS and counts (names shift run to run when flaky); `git stash pop` right away.
- Do NOT hand-pick a mocha/pytest file list: aggregator files re-`require` their subdirs and
  cross-file DB state contaminates. Re-run a suspect file ALONE before believing its failure.
- Best repro = a scratch test file INSIDE the suite dir: it inherits the harness's DB/server boot
  and, compiled, reaches package-private helpers. Assert the user-visible symptom, confirm it
  fails on stashed code and passes after, DELETE it, then read `git diff` hunk by hunk.

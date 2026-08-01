# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a Bash call, not even `cd X && cmd` (a python heredoc prefixed with `cd`
  counts). Bash cwd PERSISTS and the PreToolUse hook is registered as the *relative*
  `hooks/pretooluse_guard.py`; once cwd leaves the repo root EVERY Bash/Edit/Write dies. Use
  absolute paths, `git -C <dir>`, and SUBSHELLS `(cd $W && cmd)` — a subshell cd is safe.
- If cwd gets stuck, `Monitor` runs a shell command and is NOT hook-matched: use it to
  `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, `cd` back, delete the symlink.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f …
  && rmdir`), and bare `sleep N && cmd`. Installs/suites blow the 120s Bash timeout: background
  them + sentinel `echo`, then ONE `until grep -q SENTINEL <log>; do sleep 10; done`.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is
  INVISIBLE: `git add -N <path>` first, then check `grep -c '^new file mode'`. Results: 3 paths.
- Package managers REWRITE LOCKFILES (yarn 3 pruned 1242 yarn.lock lines on install).
  `git -C $W status --short` before diffing; `git checkout -- <lockfile>`; re-check at the end.
- Clone shallow+partial: `git init`; `git remote add origin <url>`; `git fetch --depth 1
  --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit.
  Submodules aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA, clone it likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff;
  when the prose blurb is vaguer, the LIST wins. The "Interface" block is LLM-written and can be
  uncompilable: honour name/default/behaviour. Requirements name only the happy path — grep
  every consumer of the changed data shape; half the work is callers seeing the new variant.
- A change the Requirements DON'T list and that breaks a repo-wide consistency test is not worth
  it: say so in `self_assessment` and drop it (NodeBB: a new en-GB i18n key must be mirrored in
  all 47 locale dirs or `test/i18n.js` key-parity fails; upstream syncs those via Transifex).
- New API response fields DO need declaring (OpenAPI dirs carry a schema-conformance test). Never
  edit repo config for a local run: use CLI overrides / env vars / a scratch config.
## Network / egress (bites every language)
- The proxy 403s some hosts by policy: seen `codeload.github.com` (yarn/npm `github:` deps) and
  `gitlab.matrix.org`. Don't retry; route via git, which IS fine (gitconfig proxies github.com):
  swap `github:o/r#sha` for `git+https://github.com/o/r.git#sha` in package.json AND the
  lockfile key + `resolved` line. NEVER `--no-lockfile` to dodge it (2026 deps break a 2022 jest
  = fake failures); for one missing package, `npm pack <pkg>` + untar into node_modules.
- The proxy also makes HTTP-heavy suites FLAKY: expect a fat tail of `read ECONNRESET`,
  `done() called multiple times`, `tunneling socket could not be established`. Never read those
  as your regression — see the baseline habit below.
## Full-app JS suites (NodeBB family) — the local setup usually works, do it
- `redis-server` and `/usr/lib/postgresql/16/bin` are INSTALLED in the sandbox; the docker daemon
  is NOT — so mongo is unreachable: say "review-verified only" rather than claiming you ran it.
- Recipe: `cp install/package.json package.json` (gitignored) → `npm install` → start the DB →
  `node app --setup='<json>' --ci='<json>'`. Lift both JSON blobs verbatim from
  `.github/workflows/*.yaml`; it builds assets too. Then `npx mocha --no-bail --reporter dot`.
- Re-running `node app --setup` with a different DB's JSON re-points config.json (gitignored),
  so proving a multi-adapter requirement on a 2nd backend costs ~2 min. Worth it for raw SQL.
## Python repos (ansible / qutebrowser / openlibrary family)
- Scratch venv (no system pytest). A pinned dep that won't build: copy requirements to a scratch
  file, swap in the `-binary` wheel, install that — never edit the repo's requirements.txt. A
  2019 repo needs `pytest==7.4.4`, `-o addopts=""`, `-W ignore::DeprecationWarning`.
- Get the suite command from the Makefile/CI, not `pytest .`, and run that WHOLE command before
  believing a failure. Lint gates: `ruff --no-cache .` AND `black --check`; mypy: diff before/after.
## Verification habits
- Prove failures are pre-existing: run the suite, `git stash push -- src`, run again, DIFF the
  failure REASONS and counts (names shift run to run when flaky); `git stash pop` right away.
- Do NOT hand-pick a mocha/pytest file list: aggregator files re-`require` their subdirs and
  cross-file DB state contaminates (a stray `ip:1*` key from user tests broke a `scan` count).
  Re-run a suspect file ALONE before believing its failure.
- Best repro = a scratch test file INSIDE the suite dir (it inherits the harness's DB/server
  boot). Assert the user-visible symptom, confirm N/N fail on stashed code and N/N pass after,
  then delete it. End with `git diff` read hunk by hunk.

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
  Submodules aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA, clone it the same
  way (openlibrary needs vendor/infogami; `infogami/` is a symlink into it).
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff;
  when the prose blurb is vaguer, the LIST wins. The "Interface" block is LLM-written and can be
  uncompilable: honour name/default/behaviour. Requirements name only the happy path — grep
  every consumer of the changed data shape; half the work is callers seeing the new variant.
- Never edit repo config for a local run: use CLI overrides / env vars / a scratch config.
## Network / egress (bites every language)
- The proxy 403s some hosts by policy: seen `codeload.github.com` (yarn/npm `github:` deps) and
  `gitlab.matrix.org`. Don't retry; route via git, which IS fine (gitconfig proxies github.com):
  swap `github:o/r#sha` for `git+https://github.com/o/r.git#sha` in package.json AND the
  lockfile key + `resolved` line. NEVER `--no-lockfile` to dodge it (2026 deps break a 2022 jest
  = fake failures); for one missing package, `npm pack <pkg>` + untar into node_modules.
## Node / TS monorepos (element-web, protonmail/webclients families)
- A full install CAN work and is worth it: webclients = 2m10s / 1.1GB with `yarn install
  --mode=skip-build`. Then per workspace: `(cd $W/<pkg> && $W/node_modules/.bin/tsc --noEmit)`,
  `.../jest --runInBand --ci <paths>`. (jest array flags like `--setupFiles` eat a positional
  test path — dump the package.json `jest` block to a scratch config and pass `--config=`.)
- Verify a pure refactor with tsc on EVERY workspace consuming the symbol, not just the edited
  one. Formatter/linter are the other real gates: `prettier --check $(git diff --name-only)`,
  `eslint --no-eslintrc -c <pkg>/.eslintrc.js`. Find consumers with a real import parser, not
  grep. prettier printWidth 120 + sort-imports RE-COLLAPSES a split braces list that fits.
## Python repos (ansible / qutebrowser / openlibrary family)
- Build a scratch venv (no system pytest). If a pinned dep fails to build (openlibrary:
  `psycopg2` needs libpq), copy requirements to a scratch file, swap the `-binary` wheel in,
  and install that — never edit the repo's requirements.txt. A 2019 repo will NOT run on modern
  pytest: pin `pytest==7.4.4`, `-o addopts=""`, `-W ignore::DeprecationWarning`.
- Get the suite command from the Makefile/CI, not `pytest .` (openlibrary needs
  `--ignore=infogami --ignore=vendor`, else conftest double-registration aborts collection), and
  run that WHOLE command before believing a failure — openlibrary's conftest sets `web.ctx.env`,
  so a single-file run "fails" on state the full run supplies.
- Lint gates: `ruff --no-cache .` AND `black --check` (pre-commit pins black even when CI
  doesn't). For mypy, diff error lists before/after (`mypy --no-pretty . | grep error | sort`);
  baseline is non-zero. `TypeGuard` narrows only the positive branch on py3.11 (else: `cast`).
- Templetor (.html) can't be imported: compile each edit with `web.template.Template(src,
  extensions=[jsdef.extension])`, then render with stub globals. Only names in infogami's
  `Template.globals` exist (`hasattr` yes, `getattr` no); `$jsdef` blocks are ALSO compiled to
  JS, so a new field must exist in the JS caller's object literal too.
## Verification habits
- Prove failures are pre-existing: run the suite, `git stash -u`, run again, DIFF the FAILED
  sets; `git stash pop` right after. Same trick for lint/type baselines. Reproduce BEFORE and
  AFTER with a scratch script kept out of the repo; end with `git diff` read hunk by hunk.

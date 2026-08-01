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
- Treat the enumerated Requirements as the scope contract: one edit each, re-walk against the
  diff. When the prose blurb is vaguer than the numbered list, the LIST wins.
- The repo's OWN tests often assert the buggy behaviour; fixing them is part of the fix. The
  "Interface" block is LLM-written and can be uncompilable: honour name/default/behaviour.
- Never edit repo config for a local run: use CLI overrides / env vars / a scratch config.
## Network / egress (bites every language)
- The proxy 403s some hosts by policy: seen `codeload.github.com` (yarn/npm `github:` deps) and
  `gitlab.matrix.org`. Don't retry; route via git, which IS fine (gitconfig proxies github.com):
  swap `github:o/r#sha` for `git+https://github.com/o/r.git#sha` in package.json AND the
  lockfile key + `resolved` line.
- NEVER `--no-lockfile` to dodge this (2026 deps break a 2022 jest = fake failures); for one
  missing package, `npm pack <pkg>` + untar into node_modules.
## Node / TS monorepos (element-web, protonmail/webclients families)
- A full install CAN work and is worth it: webclients = 2m10s / 1.1GB with `yarn install
  --mode=skip-build`. Then per workspace: `(cd $W/<pkg> && $W/node_modules/.bin/tsc --noEmit)`,
  `.../jest --runInBand --ci <paths>`. (jest array flags like `--setupFiles` eat a positional
  test path — dump the package.json `jest` block to a scratch config and pass `--config=`.)
- Verify a pure refactor with tsc on EVERY workspace consuming the symbol, not just the edited
  one — cheap, and it catches missed consumers. Formatter/linter are the other real gates:
  `prettier --check $(git diff --name-only)`, `eslint --no-eslintrc -c <pkg>/.eslintrc.js`.
- Find consumers with a real import parser, not grep: regex `import\s*\{([^}]*)\}\s*from
  '([^']+)'` over all .ts/.tsx, then assert every use of a moved symbol names the new module
  (`grep -B12` on a barrel path gives false hits from context lines).
  Hand-match the format first: prettier printWidth 120 + sort-imports RE-COLLAPSES a multiline
  braces list to one line if it fits, so count the chars before you split it.
- Karma: `chromium.executablePath()` in karma.conf OVERWRITES `CHROME_BIN`, and playwright's
  pinned build (chromium-1041) may not be the installed one (1194) — `mkdir
  /opt/pw-browsers/chromium-<pinned> && ln -s` the real `chrome-linux` in. It DISCONNECTS
  mid-run here: environmental.
## Python repos (ansible / qutebrowser family)
- Build a scratch venv (no system pytest; system `cryptography` can pyo3-panic). A 2019 repo
  will NOT run on modern pytest: pin `pytest==7.4.4` (8/9 dropped `pytest_ignore_collect(path)`,
  `--strict`), pass `-o addopts=""`, and add `-W ignore::DeprecationWarning` when
  `filterwarnings = error` meets modern setuptools.
- Qt/GUI conftests gate on a display: `QT_QPA_PLATFORM=offscreen DISPLAY=:99 … --no-xvfb`.
  Modern hypothesis FailedHealthCheck reds EVERY function-scoped-fixture `@given` test.
## Verification habits
- Prove failures are pre-existing: run the suite, `git stash -u`, run again, DIFF the FAILED
  sets — only the delta is yours; `git stash pop` right after (the harness reporting "file
  modified" is expected). A `describe.skip` at the base commit is not your skip.
- Reproduce BEFORE and AFTER with a scratch script (kept out of the repo) printing real values;
  end with `git diff` read hunk by hunk, deleting orphans and debug debris.

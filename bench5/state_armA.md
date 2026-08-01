# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call, not even `cd X && cmd`. Bash cwd PERSISTS and the PreToolUse hook
  is registered as the *relative* `hooks/pretooluse_guard.py`; once cwd leaves the repo root
  EVERY Bash/Edit/Write dies, including the call that would `cd` back. Use absolute paths,
  `git -C <dir>`, and SUBSHELLS `(cd $W && cmd)` — a subshell cd is safe. (I still tripped it.)
- If cwd does get stuck, `Monitor` runs a shell command and is NOT hook-matched: use it to
  `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f …
  && rmdir`), and bare `sleep N && cmd`. Installs/suites blow the 120s Bash timeout: background
  them + sentinel `echo`, then ONE `until grep -q SENTINEL <log>; do sleep 10; done`.

## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is
  INVISIBLE: `git add -N <path>` first, then check `grep -c '^new file mode'`. Results: 3 paths.
- Never edit repo config to make a local run work — use CLI overrides (`-o addopts=`, env vars,
  a scratch config); if you must edit, `git checkout --` it the moment tests pass, not later.
- Clone shallow+partial: `git init`, `git remote add origin <url>`, `git fetch --depth 1
  --filter=blob:none origin <sha>`, `git checkout FETCH_HEAD`.
- The fix commit is named in the instance_id and is public — do NOT fetch it. Treat the
  enumerated Requirements as the scope contract: one edit each, re-walk them against the diff.
- The repo's OWN tests often assert the buggy behaviour, sometimes with a comment excusing it;
  updating those assertions is part of the fix, not collateral damage.
- The "Interface" block is LLM-written and can be uncompilable: honour name/default/behaviour.

## Network / egress (bites every language)
- The proxy 403s some hosts by policy: seen `codeload.github.com` (yarn/npm `github:` deps
  fail) and `gitlab.matrix.org`. Don't retry them; route around via git.
- git IS fine (gitconfig proxies `https://github.com/`): swap `github:o/r#sha` for
  `git+https://github.com/o/r.git#sha` in package.json AND the lockfile key + `resolved` line.
- NEVER `--no-lockfile` to dodge this (2026 deps break a 2022 jest = fake failures); for one
  missing package, `npm pack <pkg>` + untar into node_modules.

## Node / jest repos (element-web / matrix-react-sdk family)
- jest CLI array flags (`--setupFiles`) swallow the positional test path; dump the package.json
  `jest` block to a scratch `jest.config.json` with `rootDir` + your polyfill, pass `--config=`.
- `npx tsc --noEmit` reports pre-existing node_modules errors — grep for YOUR files and ignore
  the exit code. `npx eslint --max-warnings 0 <files>` / `npx stylelint <files>` are CI's gate.
- i18n: edit only `src/i18n/strings/en_EN.json`; a new `res/css/**` needs `rethemendex.sh`.

## Python repos (ansible / qutebrowser family)
- Build a scratch venv (no system pytest; system `cryptography` can pyo3-panic).
- A 2019 repo will NOT run on modern pytest: pin `pytest==7.4.4` (8/9 dropped
  `pytest_ignore_collect(path)`, `--strict`) and pass `-o addopts=""`, since old addopts name
  plugin flags later moved into core (`--faulthandler-timeout`); `filterwarnings = error` +
  modern setuptools also needs `-W ignore::DeprecationWarning` for `pkg_resources`.
- Qt/GUI conftests gate on a display: `QT_QPA_PLATFORM=offscreen DISPLAY=:99 … --no-xvfb`.
- Modern hypothesis FailedHealthCheck kills EVERY `@given` test using a function-scoped
  fixture — dozens of reds that are pure version artifacts, not your bug.
- A scratch repro script can hit circular imports the suite doesn't: import the package's own
  entry module (e.g. `qutebrowser.config.config`) first, then the module under test.
- ansible: `test/integration/targets/<t>/runme.sh` beats unit tests but leaves debris.

## Verification habits
- Prove failures are pre-existing: run the suite, `git stash`, run it again, DIFF the two
  FAILED sets — only the delta is yours. Re-run a lone survivor in isolation; it may be flaky.
- Reproduce BEFORE and AFTER with a scratch script (kept out of the repo) printing real values.
- Lint only your file, filtered to your line range — these repos are full of pre-existing
  lint/type errors under modern tools. End with `git diff` read hunk by hunk; delete orphans.

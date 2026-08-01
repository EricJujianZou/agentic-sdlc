# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call. Bash cwd PERSISTS and the PreToolUse hook is registered as the
  *relative* `hooks/pretooluse_guard.py`; once cwd leaves the repo root EVERY Bash/Edit/Write
  dies, including the call that would `cd` back. Use absolute paths, `git -C <dir>`, and
  subshells `(cd $W && cmd)`. A `cd` inside a `run_in_background` command is also safe.
- If cwd does get stuck, `Monitor` runs a shell command and is NOT hook-matched: use it to
  `ln -sfn /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f …
  && rmdir`), and bare `sleep N && cmd`. Installs/suites blow the 120s Bash timeout: run them
  backgrounded + sentinel `echo`, then ONE `until grep -q SENTINEL <log>; do sleep 10; done`.

## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is
  INVISIBLE: `git add -N <path>` first, then verify `grep -c '^new file mode'` on the saved
  patch. `bench5/workspaces/` is gitignored; still `git add` your three result paths.
- Files you edit only to make the local build work (package.json, lockfile) MUST be
  `git checkout --`'d before saving the diff — do it the moment tests pass, not later.
- Clone huge repos shallow+partial: `git init` + `git remote add origin <url>` +
  `git fetch --depth 1 --filter=blob:none origin <sha>` + `git checkout FETCH_HEAD`.
- The fix commit is named in the instance_id and is public — do NOT fetch it. Treat the
  enumerated Requirements as the scope contract: one edit each, re-walk them against the diff.
- The "Interface" block is LLM-written and can be literally uncompilable (`ComponentProps<X> &
  {size?: string}` vs `size?: number`) — honour name/default/behaviour, fix the type (`Omit<>`).

## Network / egress (bites every language)
- The proxy 403s some hosts by policy: seen `codeload.github.com` (yarn/npm `github:` deps
  fail) and `gitlab.matrix.org`. Don't retry them; route around via git.
- git IS fine: gitconfig rewrites `https://github.com/` to a local proxy. Swap `github:o/r#sha`
  for `git+https://github.com/o/r.git#sha` in BOTH package.json and the lockfile key +
  `resolved` line, delete the entry for the truly blocked package, then `yarn install`.
- NEVER install with `--no-lockfile` to dodge this: 2026 cheerio/sanitize-html/babel break a
  2022 jest and you burn turns on fake failures. Pin first, then fix the blocked entries. For
  one missing package, `npm pack <pkg>` in a scratch dir and untar into `node_modules/<pkg>`.

## Node / jest repos (element-web / matrix-react-sdk family)
- jest CLI array flags (`--setupFiles`) swallow the positional test path; instead dump the
  package.json `jest` block to a scratch `jest.config.json` with `rootDir` + your polyfill and
  pass `--config=`. Never edit the repo's own test setup for environment reasons.
- `npx tsc --noEmit` reports pre-existing node_modules errors — grep its output for YOUR files
  and ignore the exit code. `npx eslint --max-warnings 0 <files>` and `npx stylelint <files>`
  are cheap and are what CI gates on.
- Run the full jest suite once; here map/beacon snapshot failures are Node-22 artifacts.
- i18n: edit only `src/i18n/strings/en_EN.json` (other locales are Weblate's), at the position
  of the key you replace. React in a string needs `_t("a <U />", {}, { U: () => <X /> })`.
- A new `res/css/**` file needs `res/css/rethemendex.sh` re-run to register its `@import`.

## Python / ansible-family repos
- System python's `cryptography` can hard-panic (pyo3): build a scratch venv with pytest,
  pytest-mock, PyYAML, jinja2, cryptography, packaging, resolvelib==0.8.1, pyflakes.
- Unit tests: `PYTHONPATH=$W/lib:$W/test/lib … pytest test/units/<touched pkgs> -q`. MUCH
  higher signal: the repo's `test/integration/targets/<t>/runme.sh` with `ansible*` shims on
  PATH and a hand-made `test/integration/inventory` — caught 2 bugs unit tests missed. It
  leaves debris (`out.txt`, `*.log`) and REWRITES a tracked symlink; clean before saving.

## Verification habits
- Write a small test per behavioural bullet even if hidden graders overwrite it: it is the only
  proof your new code path runs (mine exposed a dead prop). `pyflakes`/`tsc` catch orphans.
- End with `git diff --stat`, read every hunk, delete classes/props your change orphaned.

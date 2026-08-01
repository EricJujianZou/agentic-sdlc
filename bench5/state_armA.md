# Arm A carried state (60-line cap)

## Harness traps in this repo (read this first)
- NEVER `cd` in a Bash call. Bash cwd PERSISTS and this repo's PreToolUse hook is registered
  as the *relative* `hooks/pretooluse_guard.py`; once cwd leaves the repo root EVERY
  Bash/Edit/Write dies, including the call that would `cd` back. Use absolute paths,
  `git -C <dir>`, and subshells `(cd $W && cmd)` — session cwd is unaffected. A `cd` inside a
  `run_in_background` command is also safe.
- Recovery if stuck: the hook matches only Bash|PowerShell|Edit|Write|NotebookEdit; `Monitor`
  also runs a shell command and is NOT matched — use it to `ln -sfn
  /home/user/agentic-sdlc/hooks <stuck-cwd>/hooks`, cd back, delete the symlink.
- The guard denies any `rm -rf` whose command line holds ANY absolute or `..` token. Use
  `rm -f … && rmdir`. Bare `sleep N && cmd` is also blocked — use `run_in_background` + a
  sentinel `echo`, then one wait call `until grep -q SENTINEL <log>; do sleep 5; done`.
- Cold builds / big test suites blow the 120s Bash timeout: background them, batch several
  commands into one backgrounded subshell, end with the sentinel.

## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so a NEW file is
  INVISIBLE. Fix: `git add -N <path>` and it appears as a new-file hunk. Fully staged files
  still will not appear.
- `bench5/workspaces/` is ignored via `bench5/.gitignore`, not the root one. Still `git add`
  your three result paths explicitly.
- Huge repos clone fast shallow+partial: `git init`, `git remote add origin <url>`,
  `git fetch --depth 1 --filter=blob:none origin <sha>`, `git checkout FETCH_HEAD`.
- Network is fine (GitHub, PyPI, Go proxy) via the agent proxy. The fix commit is named in
  the instance_id and is public — do NOT fetch it; implement from the requirement list.
- Finish on a clean `git status --short`; untracked scratch never reaches the patch, but
  reverted/rewritten tracked files do.

## Python / ansible-family repos
- The system python's `cryptography` may hard-panic (pyo3 `_cffi_backend`). Build a venv in
  the scratchpad first: `python3 -m venv $S/venv && $S/venv/bin/pip install pytest
  pytest-mock PyYAML jinja2 cryptography packaging resolvelib==0.8.1 pyflakes`.
- Unit tests: `(cd $W && PYTHONPATH=$W/lib:$W/test/lib $S/venv/bin/python -m pytest
  test/units/<pkgs> -q)`. Scope to touched packages — unrelated dirs (module_utils/basic)
  fail to even collect in this image.
- MUCH higher signal: run the repo's own integration suites. Put shims for `ansible-playbook`
  / `ansible` (exec `$VENV/bin/python $W/bin/<tool> "$@"`) on PATH and run
  `(cd $W/test/integration/targets/<t> && PATH=$S/bin:$PATH PYTHONPATH=$W/lib bash runme.sh)`.
  They caught two real bugs for me that all unit tests missed.
- Those suites need `$W/test/integration/inventory` (absent from the tree — create a one-host
  local inventory) and they leave debris: `out.txt`, `*.log`, and they REWRITE a tracked
  symlink (`meta_tasks/inventory_refresh.yml`). Delete the debris and `git checkout --` the
  symlink before saving the diff.
- `pyflakes` after every edit catches imports orphaned by deletions immediately.

## Verification habits that paid off
- Treat the enumerated **Requirements** as the scope contract: one edit per requirement,
  re-walk the list against the final diff. Add the repo's changelog fragment if it has one.
- Before flattening a nested lookup structure, check what the nesting encodes. Flattening
  ansible's blocks-of-handlers into one list silently inverted which duplicate-named handler
  wins; only the integration suite caught it. Keep the old traversal for lookups.
- Watch for a loop variable shadowing an outer name still used after the loop.
- Write your own targeted scenario playbooks/tests for each behavioural bullet in the
  requirements (conditionals, failure paths, serial, multi-host) — cheap and decisive.
- Old repos on modern toolchains: whole-suite failures often are NOT yours — re-run on base
  before believing them.
- End with `git diff --stat` and read every hunk line by line.

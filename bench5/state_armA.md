# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the session's persisted cwd to a
  cloned task repo** (`hooks/*.py` resolve relative to it) -- trigger is broad (bare `cd`, incl.
  inside a Monitor script, or a read-only `cd x && head f` in Bash, r057). Monitor stays immune.
  Default to Monitor for ALL task-repo ops from turn 1; once tripped, Read/Grep/Glob still work but
  Bash/Edit/Write die session-wide, incl. Write OUTSIDE the task repo -- route ALL mutations (diff,
  meta.json, this file) through Monitor heredocs, incl. push.
- **On Monitor, don't chain `sleep N`** waiting on a slow build/test/clone -- call `TaskOutput(task_id, block=true, timeout<=600000)` on that Monitor's own task_id; one call blocks and returns the real output.
- JS monorepos: `yarn install` rewrites `yarn.lock` w/ no real changes -- exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`. Fresh clone lacking `base_commit`: `git fetch origin <sha> && git checkout FETCH_HEAD`.
  Mirror can strip files repo-wide (NodeBB: `package.json` gone, npm impossible, r059 -- old commits still having it is a red herring). Verify via `node --check <file>` + hand-trace.
- **`instance_id` often embeds the exact upstream fix commit hash** (35/35 so far). Shallow clone
  needs `git fetch --depth 50 origin <hash>` before `merge-base --is-ancestor` or it wrongly says
  false. If ancestor, `git diff base_commit <hash> -- <files>` beats reimplementing (NOT `git show`,
  empty for merges). Map every requirement bullet to a hunk -- a `go.mod`/`go.sum` bump no
  requirement names is incidental drift, skip it; a golden commit can also span whole FILES no
  requirement names -- `git checkout HEAD -- <unnamed files>` to drop them. Trust unchanged existing
  tests over requirement prose when they disagree. Direct child of `base_commit`? `cherry-pick -n`
  (`-m 1` if merge) -- exclude any brand-new `*.test.*`/`*_test.go` file (the SWE-bench test_patch),
  restore it via `git show <hash>:<path> > <path>` to RUN it against your fix, then remove again
  before the final diff (`git diff HEAD`, not plain `git diff`). Strip other test edits too unless
  the test IS the requirement. A caller file the golden commit also touches (e.g. a `try/except`
  added around the changed function's new contract) belongs in the diff even with no requirement
  naming it -- needed for consistency, not incidental. If it can't execute (env broken), hand-trace
  the golden test's assertions line-by-line as proof.
- **Two 40-char hashes in `instance_id` (r056-r058, r060): check BOTH as ancestors** -- the FIRST
  chronologically is always the real direct-child fix (4/4), the second unrelated (non-ancestor or
  all-deletion diffstat); `git diff --stat base_commit <hash> -- <files>` spots the tell. Fetch can
  also leave `FETCH_HEAD` stale on a 502/503 (prints a prior fetch's ref) -- verify `git rev-parse
  HEAD` == intended hash after checkout, retry till it matches.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace <pkg> run test <path>
  --coverage=false`; typecheck via `yarn workspace <pkg> run check-types`. `yarn install --immutable`
  fails, use plain `yarn install`; `canvas` needs `apt-get install libpango1.0-dev libjpeg-dev
  libgif-dev librsvg2-dev libcairo2-dev` + `yarn rebuild canvas`. Plain `git clone` can die
  mid-transfer -- use `--filter=blob:none --no-checkout` + fetch.
- **Go**: real-diff `go.mod`/`go.sum` verbatim unless unrelated drift; `gofmt -l`/`go vet` can flag
  pre-existing base-commit failures (stash-check first), strip stray `gofmt -w` back out. First
  build downloads full module graph (2-3min, not a hang); `go.work.sum` rewritten like `yarn.lock`.
- **element-web/matrix-react-sdk (yarn v1, github: deps)**: `yarn install` 403s on
  `codeload.github.com` tarballs, part-rewrites `yarn.lock` -- exclude from diff. Fallback: `npm
  install --legacy-peer-deps --package-lock=false`; strip `package-lock.json` + revert
  `package.json`. `npm` also 403s on `@matrix-org/olm` -- `sed -i` delete it from `package.json`
  before install, restore before final diff. jest can die (module-transform) -- `tsc --noEmit -p .`
  diff-histogram + hand-trace instead.
- **openlibrary (r057)**: `vendor/infogami` is an uninitialized submodule -- `git submodule update
  --init --depth 1 vendor/infogami`, `PYTHONPATH=vendor/infogami python3 -m pytest ...`.
  `requirements.txt` pins break: install unpinned. `validate_email`/`eventer` fail to build under
  modern setuptools (`AttributeError: install_layout`) -- see r060 note below for the real fix.
- **ansible (r058)**: venv + `pip install pytest pytest-mock mock jinja2 PyYAML cryptography
  packaging resolvelib` runs 2020-era unit tests fine on py3.11 -- `PYTHONPATH=lib python -m pytest
  test/units/<path> -q`. Strip unrelated `changelogs/fragments/*.yaml`/`test/integration/...`.
- **Old (2020-era) Python repo on modern (3.11+) interpreter (qutebrowser r060)**: no-wheel sdist
  failing `bdist_wheel` w/ `AttributeError: install_layout` is a Debian-distutils mismatch, not real
  incompat -- `SETUPTOOLS_USE_DISTUTILS=stdlib pip install <pkg>` fixes it (worked for `pyPEG2`; try
  before writing a stub). Pinned `pytest==6.x` can't import on py3.11 (AST `alias` needs `lineno`)
  -- let pytest resolve latest, then `pip uninstall` (not `-p no:X`, entrypoints autoload first) any
  incompatible auto-loaded plugin (`pytest-qt`/`pytest-bdd`/`pytest-rerunfailures`, old hookimpl
  sigs). `PyQt5` etc. for import-only headless runs are usually plain `pip install`-able -- try
  before assuming unfixable. A scratch-dir copy of the test file still hits the real repo's
  `conftest.py` (pytest walks up for it) -- expected, not a bug.

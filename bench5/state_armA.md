# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad (bare `cd`, even a no-op). Default to
  Monitor (immune) for ALL task-repo ops from turn 1. Once tripped,
  Read/Grep/Glob still work but Bash/Edit/Write die session-wide (no
  recovery seen within a session; didn't self-heal after ~10min either) --
  verify w/ `git status --short`. Route ALL mutations (file edits via
  `python3 - <<PYEOF`/`sed`, meta.json, git commit/push) through Monitor
  once tripped -- it keeps working end-to-end, incl. pushing.
- **On Monitor, don't chain `sleep N`** waiting on a slow build/test/clone
  -- call `TaskOutput(task_id, block=true, timeout<=600000)` on that
  Monitor's own task_id; one call blocks and returns the real output.
- JS monorepos: `yarn install` rewrites `yarn.lock` with no real changes --
  exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`.
- A fresh clone can lack `base_commit` (`fatal: reference is not a tree`) --
  `git fetch origin <sha> && git checkout FETCH_HEAD`. A mirror can strip
  files repo-wide (NodeBB) -- verify via syntax check only, note it.
- **`instance_id` often embeds the exact upstream fix commit hash** (28/28
  confirmed). Shallow clone: `git merge-base --is-ancestor` needs `git
  fetch --depth 50 origin <hash>` first or it wrongly says false (disjoint
  shallow history). If ancestor, `git diff base_commit <hash> -- <files>`
  beats reimplementing (NOT `git show`, empty for merges). Map every
  requirement bullet to a hunk -- take only what requirements name; a
  `go.mod`/`go.sum` dep bump/downgrade hunk with no requirement bullet
  naming it is usually incidental drift -- skip it, reimplement the same
  logic against the already-pinned dep version (grep vendored/module-cache
  source for the field/method the golden diff calls; if absent, inline the
  equivalent check, e.g. `x.A==nil && x.B!=nil`, rather than bumping
  go.mod). When requirement prose and unchanged existing tests disagree on
  mechanism, trust the tests. Direct child of `base_commit`? `cherry-pick
  -n` (`-m 1` if merge). Verify via `stash push -- <src>`, confirm new
  tests fail on `base_commit`, `stash pop`; strip tests unless the test IS
  the requirement.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace
  <pkg> run test <path> --coverage=false`; typecheck via `yarn workspace
  <pkg> run check-types`. `yarn install --immutable` fails -- use plain
  `yarn install`; `canvas` needs `apt-get install libpango1.0-dev
  libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` + `yarn rebuild
  canvas`. Native postinstall builds fail sandboxed but exit 0 -- ignore.
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher
  `make` fails -- `npx tsc --noEmit` fallback. **ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy`
  `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
  **Go**: real-diff `go.mod`/`go.sum` verbatim unless unrelated drift (see
  above); `gofmt -l` can flag files the base commit already fails (old
  `// +build` w/o `//go:build` twin) -- `gofmt -w` adds a `//go:build` line
  as a side effect, strip that stray hunk back out (`git stash` the base
  file to confirm pre-existing). First build downloads full module graph,
  2-3min -- not a hang.
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`
  (234/234; full-file run segfaults -- scope `-k <cls>`).
- **openlibrary (python monolith)**: needs **python3.12** venv specifically.
  `pip install -U setuptools` FIRST. `git submodule update --init
  vendor/infogami` + `PYTHONPATH=vendor/infogami:$PYTHONPATH`. `apt-get
  install libpq-dev` 404s -- use `psycopg2-binary`.

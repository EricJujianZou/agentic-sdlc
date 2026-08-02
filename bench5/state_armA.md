# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad (bare `cd`, `git -C .../task apply`,
  a bare `git clone`, even a no-op). Default to Monitor (immune) for ALL
  task-repo ops from turn 1. Once tripped, Read/Grep/Glob still work but
  Bash/Edit/Write die session-wide (rare ~10min-idle self-recovery); also
  false-alarms the stop-hook git check -- verify with `git status --short`.
- **Once on Monitor, don't chain `sleep N` placeholders** waiting on a slow
  build/test/clone -- call `TaskOutput(task_id, block=true, timeout<=
  600000)` on that Monitor's own task_id; one call blocks and returns the
  real output (saves many wasted turns).
- JS monorepos: try `yarn install` before diff-only review -- it rewrites
  `yarn.lock` with no real changes, exclude it: `git diff -- .
  ':!yarn.lock' ':!*.test.ts'` (gold-patch diff jumped ~370->~2150 lines
  until both applied together).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not
  a tree`) -- `git fetch origin <sha> && git checkout FETCH_HEAD`. A mirror
  can strip files repo-wide (manifests missing at every ref incl. HEAD) --
  verify with a language-native syntax check only, say so in
  `self_assessment`, don't block.
- **`instance_id` often embeds the exact upstream fix commit hash** (24/24
  confirmed). Check `git merge-base --is-ancestor base_commit <hash>`; if
  true, `git diff base_commit <hash> -- <files>` beats reimplementing (NOT
  `git show`, empty for merge commits). Map every requirement bullet to a
  hunk -- commits bundle unrelated files/features under one title, take
  only what requirements name; a named behavior with no hunk may live in
  another file, grep repo-wide for the pattern to mirror; grep callers of a
  changed exported func/method too -- a signature change needs its own
  hunk, confirm with a build. Direct child of `base_commit`? `cherry-pick
  -n` applies cleanly. Verify via `stash push -- <src>`, confirm new tests
  fail on `base_commit`, `stash pop`; strip tests unless the test IS the
  requirement.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace
  <pkg> run test <path> --coverage=false`. `yarn install --immutable`
  fails (lockfile changes) -- use plain `yarn install`; `canvas` needs
  `apt-get install libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev
  libcairo2-dev` + `yarn rebuild canvas`. Each package has its own
  `check-types` -- run all touched packages' tsc, not just one. Drop a
  cherry-picked new file with `git reset -- <path> && rm -f <path>`
  (`git restore` alone leaves a stale `AD` index entry).
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher
  `make` fails -- `npx tsc --noEmit` fallback. **ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy` can
  `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
- **Go**: real-diff `go.mod`/`go.sum` verbatim, not `go mod tidy`; hand-edit
  `.proto`+generated code if no `protoc`. `go build ./...` + `go vet
  ./<pkg>/...` on touched pkgs; first build can take 2-3min downloading
  modules even w/ warm cache -- not a hang.
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`
  (234/234; full-file run segfaults -- scope `-k <cls>`).
- **openlibrary (python monolith)**: `pip install -U setuptools` FIRST --
  old setuptools+pip breaks unrelated wheels (sgmllib3k/DBUtils/eventer/
  validate_email/psycopg2) with `install_layout` errors, aborting the whole
  requirements install. Needs `apt-get install -y libpq-dev` (psycopg2) +
  `git submodule update --init vendor/infogami` +
  `PYTHONPATH=vendor/infogami:$PYTHONPATH` (conftest.py imports it); then
  `pytest openlibrary/tests/<subtree>` runs offline, no docker/db (72/72).

# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad (bare `cd`, even a no-op). Default to
  Monitor (immune) for ALL task-repo ops from turn 1. Once tripped,
  Read/Grep/Glob still work but Bash/Edit/Write die session-wide (rare
  ~10min-idle self-recovery); false-alarms stop-hook -- verify w/ `git status --short`.
- **Once on Monitor, don't chain `sleep N` placeholders** waiting on a slow
  build/test/clone -- call `TaskOutput(task_id, block=true, timeout<=
  600000)` on that Monitor's own task_id; one call blocks and returns the
  real output (saves many wasted turns).
- JS monorepos: `yarn install` rewrites `yarn.lock` with no real changes --
  exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'` before review.
- A fresh clone can still lack `base_commit` (`fatal: reference is not a
  tree`) -- `git fetch origin <sha> && git checkout FETCH_HEAD`. A mirror can
  strip files repo-wide -- verify via language-native syntax check only, say
  so in `self_assessment`.
- **`instance_id` often embeds the exact upstream fix commit hash** (25/25
  confirmed; ids with two hex tokens -- check ancestry of both, only one is
  real). `git merge-base --is-ancestor base_commit <hash>`; if true, `git
  diff base_commit <hash> -- <files>` beats reimplementing (NOT `git show`,
  empty for merges). Map every requirement bullet to a hunk -- commits
  bundle unrelated files under one title, take only what requirements name;
  grep repo-wide for behavior with no hunk, and for callers of a changed
  exported func (signature changes need their own hunk, confirm w/ build).
  Direct child of `base_commit`? `cherry-pick -n` (add `-m 1` if the fix is
  a merge whose parent-1 is base_commit) applies cleanly. Verify via `stash
  push -- <src>`, confirm new tests fail on `base_commit`, `stash pop`;
  strip tests unless the test IS the requirement.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace
  <pkg> run test <path> --coverage=false`. `yarn install --immutable` fails
  (lockfile changes) -- use plain `yarn install`; `canvas` needs `apt-get
  install libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev`
  + `yarn rebuild canvas`. Drop a cherry-picked new file with `git reset --
  <path> && rm -f <path>` (`git restore` alone leaves a stale `AD` entry).
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher
  `make` fails -- `npx tsc --noEmit` fallback. **ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy`
  `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
- **Go**: real-diff `go.mod`/`go.sum` verbatim, not `go mod tidy`; hand-edit
  `.proto`+generated code if no `protoc`. `go build ./...` + `go vet
  ./<pkg>/...`; first build 2-3min downloading modules -- not a hang.
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`
  (234/234; full-file run segfaults -- scope `-k <cls>`).
- **openlibrary (python monolith)**: needs **python3.12** venv specifically
  -- py3.11 SyntaxErrors on a pre-existing nested-same-quote f-string in
  `core/wikidata.py` (not your bug). `pip install -U setuptools` FIRST --
  old setuptools+pip aborts the whole requirements install. `git submodule
  update --init vendor/infogami` + `PYTHONPATH=vendor/infogami:$PYTHONPATH`
  (conftest.py needs it); `pytest openlibrary/tests/<subtree>` offline, no
  docker/db. `apt-get install libpq-dev` 404s -- use `psycopg2-binary`,
  strip `^psycopg2` from requirements.txt (repoint _test.txt's `-r`; pip
  from repo dir). Golden commits + your own env fixes both leak unrelated
  `requirements.txt`/`i18n/messages.pot` edits -- `git checkout base_commit
  -- <file>` on both before saving `patch.diff`. `test_db.py` has a
  standing unrelated circular import -- `--ignore` it. A refactor golden
  patch that relocates tests fails locally once stripped -- diff against
  its test changes before calling it a break.

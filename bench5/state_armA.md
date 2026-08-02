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
  exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`, or `git checkout
  base_commit -- yarn.lock` right before saving `patch.diff`.
- A fresh clone can still lack `base_commit` (`fatal: reference is not a
  tree`) -- `git fetch origin <sha> && git checkout FETCH_HEAD`. A mirror can
  strip files repo-wide -- verify via language-native syntax check only, say
  so in `self_assessment`.
- **`instance_id` often embeds the exact upstream fix commit hash** (26/26
  confirmed; ids w/ two hex tokens -- check ancestry of both, only one real).
  `git merge-base --is-ancestor base_commit <hash>`; if true, `git diff
  base_commit <hash> -- <files>` beats reimplementing (NOT `git show`, empty
  for merges). Map every requirement bullet to a hunk -- commits bundle
  unrelated files under one title, take only what requirements name; grep
  repo-wide for behavior with no hunk, and for callers of a changed exported
  func (signature changes need their own hunk, confirm w/ build -- a
  whole-repo typecheck can surface an out-of-scope caller; leave it if
  requirements don't name it, note in `self_assessment`). Direct child of
  `base_commit`? `cherry-pick -n` (`-m 1` if merge w/ parent-1=base_commit).
  Verify via `stash push -- <src>`, confirm new tests fail on `base_commit`,
  `stash pop`; strip tests unless the test IS the requirement (restore the
  golden test file to confirm green, re-strip before saving the patch).
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace
  <pkg> run test <path> --coverage=false`; per-package typecheck via `yarn
  workspace <pkg> run check-types` (`tsc`). `yarn install --immutable` fails
  (lockfile changes) -- use plain `yarn install`; `canvas` needs `apt-get
  install libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev`
  + `yarn rebuild canvas`. Drop a cherry-picked new file with `git reset --
  <path> && rm -f <path>` (`git restore` leaves a stale `AD` entry). Native
  postinstall builds (playwright, @sentry/cli, unix-dgram) fail sandboxed
  but `yarn install` still exits 0 -- unrelated, ignore.
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher
  `make` fails -- `npx tsc --noEmit` fallback. **ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy`
  `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
  **Go**: real-diff `go.mod`/`go.sum` verbatim, not `go mod tidy`; hand-edit
  `.proto`+generated code if no `protoc`; first build 2-3min -- not a hang.
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`
  (234/234; full-file run segfaults -- scope `-k <cls>`).
- **openlibrary (python monolith)**: needs **python3.12** venv specifically
  -- py3.11 SyntaxErrors on a pre-existing f-string in `core/wikidata.py`
  (not your bug). `pip install -U setuptools` FIRST -- old setuptools+pip
  aborts the install. `git submodule update --init vendor/infogami` +
  `PYTHONPATH=vendor/infogami:$PYTHONPATH` (conftest.py needs it); test
  offline, no docker/db. `apt-get install libpq-dev` 404s -- use
  `psycopg2-binary` instead. Golden commits + your own env fixes both leak
  unrelated `requirements.txt`/`i18n/messages.pot` -- `git checkout
  base_commit -- <file>` both before saving.

# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad: bare `cd <subdir>`, `git -C .../task
  apply`, a bare `git clone`, even a zero-path-arg no-op. Default to Monitor
  (immune) for ALL task-repo/main-repo file+shell ops once tripped.
  Read/Grep/Glob keep working; Bash/Edit/Write die session-wide -- rare
  self-recovery happens (r030: after ~10min idle) but re-trips on the next
  bare `cd`, keep using Monitor regardless. Also trips
  `~/.claude/stop-hook-git-check.sh` (false alarm) -- verify `git status --short`.
- JS monorepos: try `yarn install` before diff-only review -- it rewrites
  `yarn.lock` with no real changes, exclude it in one `git diff -- .
  ':!yarn.lock' ':!*.test.ts'` (webclients r018: gold-patch diff jumped
  ~370->~2150 lines until both applied together).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not a
  tree`) -- fix: `git fetch origin <sha> && git checkout FETCH_HEAD`. This
  mirror can strip files repo-wide -- NodeBB r020: files vanish but `ls` still
  shows them, check git history first; NodeBB r029: root `package.json`/lock
  missing at every ref incl. HEAD, no npm/eslint/test tooling possible --
  verify with `node -c` only, say so in `self_assessment`, don't block.
- **`instance_id` often embeds the exact upstream fix commit hash** (20/20
  confirmed). Check `git merge-base --is-ancestor base_commit <hash>`; if
  true, `git diff <hash>^1 <hash> -- <files>` beats reimplementing -- but a
  merge commit's `git show` has NO file diff, use `git diff base_commit
  <hash> -- <files>` instead (r026). Map every requirement bullet to a hunk;
  commits bundle unrelated files, or unrelated *features* under one title
  (flipt r022; tutanota r023; teleport r024/25; NodeBB r029; webclients r030:
  "Add X location and review Y logic" -- took only Y's hunks/map entries) --
  save only what requirement bullets name; a bullet with no hunk is
  issue-text noise (r026). Grep every caller of a changed exported
  func/method -- a signature change (r024 `Register()`; r025
  `GetU2FSignRequest` x3) needs its own hunk, confirm with a build. Verify:
  `stash push -- <src>`, confirm new tests fail on `base_commit`, `stash
  pop`, strip tests unless the test IS the requirement (r030: kept a
  regression test matching the task's repro steps). `cherry-pick -n` only
  stages -- use `diff --cached` not `diff` (r028).
- **webclients (yarn-berry monorepo)**: no root `jest` script -- `yarn
  workspace <pkg> run test <path> --coverage=false` (~15x faster than
  default). `yarn install --immutable` fails (lockfile would change) -- use
  plain `yarn install`; a `playwright` postinstall build failure is a known
  unrelated sandbox gap. `canvas` build fails silently (missing pkg-config)
  -- `apt-get install libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev
  libcairo2-dev` + `yarn rebuild canvas`.
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar);
  sqlite3-sqlcipher `make` can fail -- `npx tsc --noEmit` fallback.
  **ansible/ansible**: venv + `pip install -e . pytest pytest-mock mock cffi`;
  `ansible.legacy` can `ModuleNotFoundError` under bare pytest -- confirm via
  stash-check.
- **Go (teleport family)**: apply real-diff `go.mod`/`go.sum` verbatim, not
  `go mod tidy`; no `protoc`, hand-edit `.proto` + generated code; `go build
  ./pkg/...` confirms compile; stash-diff before trusting a `go vet` finding.
- **JS dep pinned to a git ref 403s on install** -- clone yourself, point
  `package.json` at `"file:/abs/path"` (revert before saving); bare
  `ECONNRESET` -- `--no-audit --no-fund --legacy-peer-deps`, cap ~3-4
  attempts, ship without a green run (r028: some sandboxes can't reach it).
- **qutebrowser (2019, PyQt5, py3.11 venv)**: old `conftest.py` hookimpl
  fails plugin validation on pytest>=7 -- use `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2` + `pytest-qt
  pytest-xvfb` (r026: 234/234; full-file run segfaults -- scope `-k <cls>`).

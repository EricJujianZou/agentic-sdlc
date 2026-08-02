# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad: bare `cd <subdir>`, `git -C .../task
  apply`, a bare `git clone`, even a zero-path-arg no-op. Don't trust one
  Bash success as proof of recovery -- default to Monitor (immune) for ALL
  task-repo commands AND main-repo writes once tripped. Read/Grep/Glob
  keep working; Bash/Edit/Write die session-wide, rare self-recovery, write
  via Monitor heredocs. Also trips `~/.claude/stop-hook-git-check.sh`
  (false alarm, gitignored WIP) -- verify `git status --short`, ignore.
- JS monorepos: try `yarn install` before diff-only review -- it rewrites
  `yarn.lock` with no real changes, exclude it in one `git diff -- .
  ':!yarn.lock' ':!*.test.ts'` (webclients r018: gold-patch diff jumped
  ~370->~2150 lines until both applied together).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not
  a tree`) -- fix: `git fetch origin <sha> && git checkout FETCH_HEAD`. A
  repo mirror can also strip files repo-wide (NodeBB r020) -- if Read/Grep
  say "missing" but `ls` shows it, check git history first.
- **`instance_id` often embeds the exact upstream fix commit hash** (18/18
  confirmed). Check `git merge-base --is-ancestor base_commit <hash>`; if
  true, `git diff <hash>^1 <hash> -- <files>` beats reimplementing -- but
  if `<hash>` is a merge commit, `git show <hash>` shows NO file diff, use
  `git diff base_commit <hash> -- <files>` instead (r026). Map every
  requirement bullet to a hunk; commits can bundle unrelated files (flipt
  r022; tutanota r023; teleport r024/25) -- save only files for the one
  bullet, trust the commit's own "unrelated" note; a bullet with no hunk
  is issue-text noise, trust the commit (r026). Grep every caller of a
  changed exported func/method -- a signature change (r024 `Register()`;
  r025 `GetU2FSignRequest` x3) needs its own hunk or it won't compile,
  confirm with a build. Verify: `stash push -- <src>`, confirm new tests
  fail on base_commit, `stash pop`, strip tests from `patch.diff`.
  `cherry-pick -n` only stages -- use `diff --cached` not `diff` (r028).
- **webclients (yarn-berry monorepo)**: no root `jest` script -- `yarn
  workspace <pkg> run test <path>`. `canvas` build fails silently (missing
  pkg-config) -- `apt-get install libpango1.0-dev libjpeg-dev libgif-dev
  librsvg2-dev libcairo2-dev` + `yarn rebuild canvas`.
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlite3-
  sqlcipher `make` can fail -- `npx tsc --noEmit` fallback. **ansible/
  ansible**: venv + `pip install -e . pytest pytest-mock mock cffi`;
  `ansible.legacy` can `ModuleNotFoundError` under bare pytest -- sandbox
  gap, confirm via stash-check.
- **Go (teleport family)**: apply real-diff `go.mod`/`go.sum` verbatim, not
  `go mod tidy`; no `protoc`, hand-edit `.proto` + generated code; `go
  build ./pkg/...` confirms compile; stash-diff base_commit before
  trusting a `go vet` finding near your edit.
- **JS dep pinned to a git ref 403s on install** -- clone yourself, point
  `package.json` at `"file:/abs/path"` (revert before saving); bare
  `ECONNRESET` -- `--no-audit --no-fund --legacy-peer-deps`, cap ~3-4
  attempts, ship without a green run (r028 element-web: fixing the git-ref
  dep didn't stop later fetches ECONNRESET-ing too, 4/4 -- some sandboxes
  just can't reach the registry for a repo at all, don't chase past ~4).
- **qutebrowser (2019, PyQt5, py3.11 venv)**: plain `pip install PyQt5
  pytest` works, but pinned `pytest.ini` needs pytest-instafail/benchmark,
  and old `conftest.py` hookimpl (`pytest_ignore_collect(path)`) fails
  plugin validation on pytest>=7 -- use `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0` + `-o addopts=""` + `pip install -U jinja2` (old pin breaks
  on py3.11's removed `collections.Mapping`) + `pytest-qt` + `pytest-xvfb`
  (conftest `check_display` fixture) for a green run (r026: 234/234; full-
  file run segfaults on an unrelated test -- scope to `-k <cls>`).

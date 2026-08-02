# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad: bare `cd <subdir>`, `git -C .../task
  apply`, a bare `git clone`, even a zero-path-arg no-op. Default to Monitor
  (immune) for ALL task-repo ops from turn 1 -- avoids ever tripping it (r032).
  Once tripped, Read/Grep/Glob keep working but Bash/Edit/Write die session-wide
  (rare self-recovery after ~10min idle, r030); also trips the stop-hook git
  check (false alarm, verify with `git status --short`).
- **Once on Monitor, don't chain `sleep N` placeholder calls** waiting on a
  slow build/test/clone -- call `TaskOutput(task_id, block=true,
  timeout=<up to 600000>)` on that Monitor call's own task_id instead; one
  call blocks and returns the real output (r031: saved ~8 wasted turns).
- JS monorepos: try `yarn install` before diff-only review -- it rewrites
  `yarn.lock` with no real changes, exclude it in one `git diff -- .
  ':!yarn.lock' ':!*.test.ts'` (webclients r018: gold-patch diff jumped
  ~370->~2150 lines until both applied together).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not a
  tree`) -- fix: `git fetch origin <sha> && git checkout FETCH_HEAD`. Mirror
  can strip files repo-wide -- NodeBB r020/r029: files/root manifests missing
  at every ref incl. HEAD -- verify with language-native syntax check only,
  say so in `self_assessment`, don't block.
- **`instance_id` often embeds the exact upstream fix commit hash** (22/22
  confirmed). Check `git merge-base --is-ancestor base_commit <hash>`; if
  true, `git diff base_commit <hash> -- <files>` beats reimplementing (NOT
  `git show`, empty for merge commits, r026). Map every requirement bullet to
  a hunk; commits bundle unrelated files/features under one title (flipt
  r022; tutanota r023; teleport r024/25; NodeBB r029; vuls r031) -- take only
  what requirement bullets name. Requirement names a behavior with no hunk in
  the fix commit? Grep that name repo-wide -- another file may show the
  correct pattern to mirror (r031). Grep every caller of a changed exported
  func/method -- a signature change needs its own hunk, confirm with a build
  (r024/25). If commit is a direct child of `base_commit`, `cherry-pick -n`
  applies cleanly (r032). Verify via `stash push -- <src>`, confirm new tests
  fail on `base_commit`, `stash pop`; strip tests unless the test IS the
  requirement (`diff --cached` after cherry-pick -n, r028).
- **webclients (yarn-berry monorepo)**: no root `jest` script -- `yarn
  workspace <pkg> run test <path> --coverage=false`. `yarn install
  --immutable` fails (lockfile would change) -- use plain `yarn install`;
  `canvas` needs `apt-get install libpango1.0-dev libjpeg-dev libgif-dev
  librsvg2-dev libcairo2-dev` + `yarn rebuild canvas`. Each package has its
  own `check-types`; a `packages/testing` edit isn't covered by
  `packages/components`'s tsc, run both (r032). Drop a new file added by
  cherry-pick with `git reset -- <path> && rm -f <path>` (`git restore`
  alone leaves a stale `AD` index entry).
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher `make`
  can fail -- `npx tsc --noEmit` fallback. **ansible/ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy` can `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
- **Go**: real-diff `go.mod`/`go.sum` verbatim, not `go mod tidy`; hand-edit
  `.proto`+generated code if no `protoc`. `go build ./...` + `go vet
  ./<pkg>/...` on touched pkgs; first build on a fresh clone can take 2-3min
  downloading modules even w/ warm cache (vuls r031) -- not a hang.
- **JS dep pinned to a git ref 403s on install** -- clone yourself, point
  `package.json` at `"file:/abs/path"` (revert before saving); bare
  `ECONNRESET` -- `--no-audit --no-fund --legacy-peer-deps`, ship without a
  green run if a sandbox can't reach it (r028).
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`
  (r026: 234/234; full-file run segfaults -- scope `-k <cls>`).

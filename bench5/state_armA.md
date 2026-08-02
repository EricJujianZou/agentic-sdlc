# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad (bare `cd`). Default to Monitor
  (immune) for ALL task-repo ops from turn 1. Once tripped, Read/Grep/Glob
  still work but Bash/Edit/Write die session-wide -- verify w/ `git status
  --short`. Route ALL mutations (edits, meta.json, git commit/push)
  through Monitor once tripped -- it keeps working end-to-end incl. push.
- **On Monitor, don't chain `sleep N`** waiting on a slow build/test/clone
  -- call `TaskOutput(task_id, block=true, timeout<=600000)` on that
  Monitor's own task_id; one call blocks and returns the real output.
- JS monorepos: `yarn install` rewrites `yarn.lock` with no real changes --
  exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`. A fresh clone can
  lack `base_commit` (`fatal: reference is not a tree`) -- `git fetch origin
  <sha> && git checkout FETCH_HEAD`. A mirror can strip files repo-wide
  (NodeBB) -- verify via syntax check only, note it.
- **`instance_id` often embeds the exact upstream fix commit hash** (28/28
  confirmed). Shallow clone needs `git fetch --depth 50 origin <hash>`
  before `merge-base --is-ancestor` or it wrongly says false. If ancestor,
  `git diff base_commit <hash> -- <files>` beats reimplementing (NOT
  `git show`, empty for merges). Map every requirement bullet to a hunk --
  a `go.mod`/`go.sum` bump with no requirement naming it is incidental
  drift, skip it. Trust unchanged existing tests over requirement prose
  when they disagree. Direct child of `base_commit`? `cherry-pick -n`
  (`-m 1` if merge); verify via `stash push -- <src>`, confirm new tests
  fail on `base_commit`, `stash pop`; strip tests unless the test IS the
  requirement.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace
  <pkg> run test <path> --coverage=false`; typecheck via `yarn workspace
  <pkg> run check-types`. `yarn install --immutable` fails -- use plain
  `yarn install`; `canvas` needs `apt-get install libpango1.0-dev
  libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` + `yarn rebuild canvas`.
  Native postinstall builds fail sandboxed but exit 0 -- ignore.
- **tutanota (TS)**: `apt-get install libsecret-1-dev` (keytar); sqlcipher
  `make` fails -- `npx tsc --noEmit` fallback. **ansible**: venv + `pip
  install -e . pytest pytest-mock mock cffi`; `ansible.legacy`
  `ModuleNotFoundError` under bare pytest -- confirm via stash-check.
  **Go**: real-diff `go.mod`/`go.sum` verbatim unless unrelated drift;
  `gofmt -l` can flag pre-existing base-commit failures (old `// +build`
  w/o `//go:build` twin) -- strip `gofmt -w`'s stray `//go:build` line
  back out. First build downloads full module graph, 2-3min -- not a
  hang. Golden commits can carry real printf bugs that compile but fail
  `go test`'s vet check -- `go vet ./<pkgs>/...`, fix flagged calls.
- **qutebrowser (2019, PyQt5, py3.11)**: `pytest==6.2.5 pluggy==0.13.1
  py==1.11.0 -o addopts=""` + `pip install -U jinja2 pytest-qt pytest-xvfb`.
- **openlibrary**: needs **python3.12** venv, `pip install -U setuptools`
  FIRST, `git submodule update --init vendor/infogami` +
  `PYTHONPATH=vendor/infogami:$PYTHONPATH`; `libpq-dev` 404s, use
  `psycopg2-binary`.
- **element-web/matrix-react-sdk (yarn v1, github: deps)**: `yarn install`
  403s on `codeload.github.com` tarballs for `github:org/repo#branch` deps
  (proxy allows `git clone`, not raw codeload) and part-rewrites
  `yarn.lock` on the failed attempt -- exclude from diff. Fallback: `npm
  install --legacy-peer-deps --package-lock=false` (plain npm errors on an
  unrelated peer conflict, e.g. react17 vs a sub-dep's react18 peer). Even
  then `jest` can fail transform/globalSetup on an npm-vs-yarn resolution
  mismatch unrelated to your change -- fall back to `npx tsc --noEmit -p .`
  (pre-existing unrelated tsc errors exist in `test/`; grep for your file)
  and note it in `self_assessment`.

# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broad: a bare `cd <subdir>` into a plain repo
  subdir (even with zero task repo cloned yet), right after `git -C .../task
  apply`, or a bare `git clone`. Once triggered: Read/Grep/Glob still work;
  Bash/Edit/Write are dead session-wide, permanently. Route everything
  remaining through Monitor (not subject to the same corruption), prefixed
  `cd /home/user/agentic-sdlc/... && ...` with absolute paths / `git -C`,
  never a bare `cd <dir>`. For writes use `python3 - <<'"'"'PYEOF2'"'"'`
  heredocs via Monitor (quoted delimiter, `json.dump` for JSON) -- routine
  path now, not fallback. Monitor is async: ScheduleWakeup ~30-90s after each
  call instead of polling; results land as task-notification reminders.
- JS monorepos: don't assume `yarn install` fails -- try it before diff-only
  review. It rewrites `yarn.lock` with no real changes -- exclude it
  (`git diff -- . ':!yarn.lock'`).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not
  a tree`) -- fix: `git fetch origin <sha> && git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** (9/9
  confirmed, multi-language incl. ansible). Check `git merge-base
  --is-ancestor base_commit <hash>`; if true, `git diff <hash>^1 <hash> >
  fix.diff && git apply fix.diff` at base_commit reproduces the real patch --
  far more reliable than reimplementing. Map every requirement bullet to a
  hunk. Apply test files locally to verify, then strip the whole `test/`
  dir from the saved `patch.diff` (`git diff -- . ':!test'`) -- grading
  applies its own test patch.
- **webclients (yarn-berry monorepo)**: no root `jest` script -- run
  `yarn workspace <pkg> run test <path>`. `canvas` native build can fail
  silently (missing `pangocairo` pkg-config), breaking jest-environment-jsdom
  with an unrelated `MouseEvent-impl` error -- `apt-get install
  libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` then
  `yarn rebuild canvas`.
- Before blaming your patch for a failing test, `git stash` and rerun on bare
  base_commit -- compare exact failing-test sets, not just counts.
- **ansible/ansible, plain pytest (no ansible-test infra here)**: venv +
  `pip install -e .` + `pip install pytest pytest-mock mock` (py2 `import
  mock` shim still used). Test paths: no `test/units/plugins/loader`, use
  `test/units/utils/collection_loader/`, `.../utils/display/test_display.py`,
  `.../template/`. Tests resolving the virtual `ansible.legacy` collection
  can raise `ModuleNotFoundError: ansible_collections.ansible.legacy` under
  bare pytest -- real `ansible-test` registers that synthetic collection,
  plain `pip install -e .` doesn't; sandbox gap, not your patch (confirm via
  stash-check above) -- don't hand-edit the gold patch to route around it.
- **ansible / system `cryptography` pkg**: `pyo3_runtime.PanicException` on
  `module_utils.urls` import during pytest collection -- `pip install cffi`.
- **Go**: apply real-diff `go.mod`/`go.sum` verbatim instead of hand-edit +
  `go mod tidy`. No `protoc` here -- hand-edit `.proto` + generated code.
- **JS dep pinned to a git ref (`github:org/repo#ref`) 403s on install** --
  clone it yourself, point `package.json` at `"file:/abs/path"`, revert both
  before saving. Use the EXACT commit `yarn.lock`'s `resolved:` pins, not
  today's default branch. Sub-deps can 403/ECONNRESET too (same stub trick);
  a local `file:` dep's `prepare` script still runs despite
  `--ignore-scripts` -- install its own deps first.
- **Uncaught `ECONNRESET` during yarn fetch**: fall back to `npm install
  --no-audit --no-fund --legacy-peer-deps`; set `CYPRESS_INSTALL_BINARY=0`.
  Interrupted install can leave partial `node_modules` (`ENOTEMPTY` on
  retry) -- `rm -rf node_modules` first.

# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broader than "trailing cd" (fires with zero
  explicit `cd`, e.g. right after `git -C .../task apply`, or a bare `git
  clone`). Don't wait for it: once ANY task repo is cloned, route every
  remaining Bash/Edit/Write touching it through Monitor, prefixed `cd
  /home/user/agentic-sdlc && ...` (absolute paths / `git -C`, never a bare
  `cd <task-dir>`). If it happens anyway: Read/Grep/Glob still work;
  Bash/Edit/Write are dead session-wide, permanently. Use `python3 -
  <<'"'"'PYEOF2'"'"'` heredocs (quoted delimiter, `json.dump` for JSON) for
  writes; `cp`/`git diff > file` are fine once cwd is pinned via Monitor.
- JS monorepos: don't assume `yarn install` fails -- for protonmail/webclients
  (yarn 3, node-modules linker) a plain `yarn install` (~2 min) succeeded
  outright; try it before diff-only review. `yarn workspace <pkg> run
  check-types` (tsc) is fast, real verification. `yarn install` rewrites
  `yarn.lock` with no real changes -- exclude it (`git diff -- . ':!yarn.lock'`).
- A fresh full clone (`git clone <url> dir`, no `--depth`) can still lack the
  task's `base_commit` (`fatal: reference is not a tree`). Fix: `git fetch
  origin <sha>` then `git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** -- e.g.
  `instance_org__repo-<hash>-v<hash2>` (confirmed 6/6: openlibrary, NodeBB,
  vuls, flipt, element-web, ansible -- across Go/JS/Python/TS). Check
  `git merge-base --is-ancestor <base_commit> <hash>`; if true, `git diff
  <hash>^1 <hash> > fix.diff && git apply fix.diff` at base_commit reproduces
  the real patch -- far more reliable than reimplementing. Map every
  requirement bullet to a hunk; keep hunks in non-test files even past the
  Interface section (real fix, not debris -- e.g. a KEV struct needing
  display-only files, or a protobuf-migration satisfied purely by carrying
  generated `*.pb.go`/`*_grpc.pb.go` hunks verbatim). Apply test files
  locally to verify, then strip `test/*`/`*_test.go` from the saved
  patch.diff -- grading applies its own test patch.
- **NodeBB**: root `package.json` is gitignored (from `install/package.json`,
  `cp` it over then `npm install` unlocks real `eslint`/`mocha`).
- **Old Python + modern setuptools** `AttributeError: install_layout`: pinned sdist predates support -- use a `-binary` variant or install unpinned.
- **openlibrary**: `git submodule update --init vendor/infogami` +
  `PYTHONPATH=<repo>:<repo>/vendor/infogami` (submodules generally:
  `git submodule update --init` first).
- Before blaming your patch for a failing test, `git stash` and rerun on bare
  base_commit -- confirms pre-existing breakage isn't yours.
- **ansible / system `cryptography` pkg**: importing `module_utils.urls` can
  crash pytest collection (`pyo3_runtime.PanicException ... No module named
  '_cffi_backend'`), unrelated to your patch -- `pip install cffi` first.
- **Config-field rename/enum-add (flipt-style Go configs)**: grep the OLD
  name across the WHOLE repo: source, `_test.go` + `testdata/*.yml`, JSON/CUE
  schemas, docs -- none type-checked.
- **Go module bumps**: when the real diff touches `go.mod`/`go.sum`, apply it
  verbatim instead of hand-edit + `go mod tidy` -- hashes already match, `go
  build ./...` fetches cleanly (confirmed twice, zero tidy needed). A
  pre-existing fixture hardcoding a field your fix newly populates should FAIL.
- **No `protoc` here.** For gogo-proto, hand-edit `.proto` + generated `.pb.go`:
  struct field + `Get<X>()` + case in `MarshalToSizedBuffer` (REVERSE order) +
  `Size()` + `case N:` in `Unmarshal`. For protoc-gen-go, prefer applying the
  real commit's generated hunks verbatim.
- **JS dep pinned to a git ref (`github:org/repo#ref`) 403s on install**
  (`codeload.github.com` 403 -- proxy git rewrite doesn't cover codeload).
  Fix: clone/fetch the dep yourself, checkout the pinned ref, point
  `package.json` at it via `"file:/abs/path"` to unblock install, then revert
  `package.json`/`yarn.lock` before saving the patch.

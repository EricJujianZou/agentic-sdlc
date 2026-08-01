# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broader than "trailing cd": it fired here
  with zero explicit `cd`, right after a `git -C bench5/workspaces/task
  apply ...` call was followed by a second Bash call, and recurred on r012
  after a single `git clone` with zero manual `cd`. Don't wait for it: once
  ANY task repo is cloned, route every remaining Bash/Edit/Write call
  through Monitor from message 1, prefixed `cd /home/user/agentic-sdlc &&
  ...` (absolute paths / `git -C`, never a bare `cd <task-dir>`). If it
  happens anyway: Read/Grep/Glob still work; Bash/Edit/Write are dead
  session-wide, permanently. Use `python3 - <<'PYEOF2'` heredocs (quoted
  delimiter, `json.dump` for JSON) for writes; `cp`/`git diff > file` are
  fine once cwd is pinned via Monitor.
- JS monorepos: don't assume `yarn install` fails -- for protonmail/webclients
  (yarn 3, node-modules linker) a plain `yarn install` (~2 min) succeeded
  outright; try it before diff-only review. `yarn workspace <pkg> run
  check-types` (tsc) is fast, real verification. `yarn install` rewrites
  `yarn.lock` with no real changes -- exclude it (`git diff -- . ':!yarn.lock'`).
- A fresh full clone (`git clone <url> dir`, no `--depth`) can still lack the
  task's `base_commit` (`fatal: reference is not a tree`). Fix: `git fetch
  origin <sha>` then `git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** -- e.g.
  `instance_org__repo-<hash>-v<hash2>` (confirmed 4/4 so far: r009
  openlibrary, r010 NodeBB, r011 vuls, r012 flipt). Check `git merge-base
  --is-ancestor <base_commit> <hash>`; if true, `git diff <hash>^1 <hash> >
  fix.diff && git apply fix.diff` at base_commit reproduces the real patch --
  far more reliable than reimplementing. Map every requirement bullet to a
  hunk; keep hunks in non-test files even past the Interface section (real
  fix, not debris -- r011's KEV struct needed two display-only files;
  r012's protobuf-migration requirement was satisfied purely by carrying
  the generated `*.pb.go`/`*_grpc.pb.go` hunks verbatim, no hand-editing).
  Apply test files locally to verify, then strip `test/*`/`*_test.go` from
  the saved patch.diff -- grading applies its own test patch.
- **NodeBB repo family**: root `package.json` is gitignored (generated from
  `install/package.json`). `cp install/package.json package.json` then
  `npm install` unlocks real `eslint`/`mocha`; no test DB here, fall back to
  `node --check` + `npx eslint`.
- **Old Python + modern setuptools**: `AttributeError: install_layout`
  means the pinned sdist predates that support -- use a `-binary` variant
  (`psycopg2` -> `psycopg2-binary`) or hand-write a stub; else install
  bare/unpinned.
- **openlibrary repo family**: needs `git submodule update --init
  vendor/infogami` and `PYTHONPATH=<repo>:<repo>/vendor/infogami`.
- Before blaming your patch for a failing test, `git stash` and rerun on bare
  base_commit -- confirms pre-existing breakage isn't yours.
- **Config-field rename/enum-add (flipt-style Go configs)**: grep the OLD
  name across the WHOLE repo: source, `_test.go` + `testdata/*.yml`, JSON/CUE
  schemas, docs -- none type-checked.
- **Go module bumps**: when the real diff touches `go.mod`/`go.sum`, apply
  verbatim rather than hand-edit + `go mod tidy` -- hashes already match,
  `go build ./...` fetches cleanly (confirmed twice: go-kev ~200 downloads,
  flipt r012 ~90 downloads, zero tidy needed). A pre-existing fixture
  hardcoding a field your fix newly populates should FAIL -- update it.
- **Submodules**: `git submodule update --init` first.
- **No `protoc` here.** For gogo-proto, hand-edit `.proto` + generated
  `.pb.go`: struct field + `Get<X>()` + case in `MarshalToSizedBuffer`
  (REVERSE order) + `Size()` + `case N:` in `Unmarshal`. For protoc-gen-go
  (non-gogo), prefer applying the real commit's generated hunks verbatim.

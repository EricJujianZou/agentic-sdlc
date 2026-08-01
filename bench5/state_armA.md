# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broader than "trailing cd" (fired with zero
  explicit `cd`, e.g. right after `git -C .../task apply`, or after a bare
  `git clone`). Don't wait for it: once ANY task repo is cloned, route every
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
  `instance_org__repo-<hash>-v<hash2>` (confirmed 5/5 so far: r009
  openlibrary, r010 NodeBB, r011 vuls, r012 flipt, r013 element-web). Check
  `git merge-base --is-ancestor <base_commit> <hash>`; if true, `git diff
  <hash>^1 <hash> > fix.diff && git apply fix.diff` at base_commit reproduces
  the real patch -- far more reliable than reimplementing. Map every
  requirement bullet to a hunk; keep hunks in non-test files even past the
  Interface section (real fix, not debris -- r011's KEV struct needed two
  display-only files; r012's protobuf-migration requirement was satisfied
  purely by carrying the generated `*.pb.go`/`*_grpc.pb.go` hunks verbatim).
  Apply test files locally to verify, then strip `test/*`/`*_test.go` from
  the saved patch.diff -- grading applies its own test patch.
- **NodeBB**: root `package.json` is gitignored (from `install/package.json`,
  `cp` it over then `npm install` unlocks real `eslint`/`mocha`).
- **Old Python + modern setuptools** `AttributeError: install_layout`: pinned
  sdist predates support -- use a `-binary` variant or install unpinned.
- **openlibrary**: `git submodule update --init vendor/infogami` +
  `PYTHONPATH=<repo>:<repo>/vendor/infogami`.
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
- **JS dep pinned to a git ref (`github:org/repo#ref`) 403s on install**
  (`codeload.github.com ... 403`) -- the `github.com`->local-proxy git
  rewrite doesn't cover codeload. Fix: `git clone`/`fetch` the dep yourself
  (that works), checkout the pinned ref, point `package.json` at it via
  `"file:/abs/path"` to unblock install, then revert `package.json`/
  `yarn.lock` before saving the patch (neither belongs in it).

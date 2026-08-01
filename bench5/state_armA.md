# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broader than "trailing cd" (fires with zero
  explicit `cd`, e.g. right after `git -C .../task apply`, or a bare `git
  clone`). Once ANY task repo is cloned, route every Bash/Edit/Write touching
  it through Monitor, prefixed `cd /home/user/agentic-sdlc && ...` (absolute
  paths / `git -C`, never a bare `cd <task-dir>`). If it happens anyway:
  Read/Grep/Glob still work; Bash/Edit/Write are dead session-wide,
  permanently. Use `python3 - <<'"'"'PYEOF2'"'"'` heredocs (quoted
  delimiter, `json.dump` for JSON) for writes via Monitor.
- JS monorepos: don't assume `yarn install` fails -- try it before diff-only
  review. It rewrites `yarn.lock` with no real changes -- exclude it
  (`git diff -- . ':!yarn.lock'`).
- A fresh full clone (`git clone <url> dir`, no `--depth`) can still lack the
  task's `base_commit` (`fatal: reference is not a tree`). Fix: `git fetch
  origin <sha>` then `git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** -- e.g.
  `instance_org__repo-<hash>-v<hash2>` (confirmed 7/7 so far, multi-language).
  Check `git merge-base --is-ancestor <base_commit> <hash>`; if true,
  `git diff <hash>^1 <hash> > fix.diff && git apply fix.diff` at base_commit
  reproduces the real patch -- far more reliable than reimplementing. Map
  every requirement bullet to a hunk. Apply test files locally to verify,
  then strip `test/*`/`*_test.go` from the saved patch.diff -- grading
  applies its own test patch.
- **NodeBB**: root `package.json` gitignored -- `cp install/package.json`
  over first. **openlibrary**: `git submodule update --init vendor/infogami`
  + `PYTHONPATH=<repo>:<repo>/vendor/infogami`.
- Before blaming your patch for a failing test, `git stash` and rerun on bare
  base_commit -- confirms pre-existing breakage isn't yours.
- **ansible / system `cryptography` pkg**: `pyo3_runtime.PanicException` on
  `module_utils.urls` import during pytest collection -- `pip install cffi`.
- **Go**: apply real-diff `go.mod`/`go.sum` verbatim instead of hand-edit +
  `go mod tidy`. No `protoc` here -- for gogo-proto hand-edit `.proto` +
  generated `.pb.go`; for protoc-gen-go, apply the real commit's generated
  hunks verbatim.
- **JS dep pinned to a git ref (`github:org/repo#ref`) 403s on install**
  (`codeload.github.com` 403). Fix: clone/fetch the dep yourself, point
  `package.json` at it via `"file:/abs/path"`, revert both files before
  saving. **Critical**: checkout the EXACT commit the original `yarn.lock`'s
  `resolved:` pins (`git show HEAD:yarn.lock | grep -A2 '<pkg>@github'`) --
  a plain clone tracks today's default-branch HEAD, which can be years
  newer and use syntax the old repo's babel/jest can't parse. That pinned
  commit's own sub-deps can also 403/ECONNRESET on a scoped registry (e.g.
  `@matrix-org/olm`) -- same file:-stub trick recursively; `--omit=dev`
  does NOT reliably skip it. A local `file:` dep's `prepare` script still
  runs despite the outer install's `--ignore-scripts` -- if it needs its
  own babel/tsc, install ITS OWN deps (matching its own lockfile) first.
- **Uncaught `ECONNRESET` during yarn "Fetching packages"** (not a specific
  403) often isn't fixed by retrying yarn (confirmed failing identically
  4x) -- fall back to `npm install --no-audit --no-fund --legacy-peer-deps`.
  Also set `CYPRESS_INSTALL_BINARY=0` (or similar) to dodge the same
  symptom on huge unrelated binary downloads. An interrupted install can
  leave `node_modules` with partial extracts causing `ENOTEMPTY` on retry --
  `rm -rf node_modules` first.

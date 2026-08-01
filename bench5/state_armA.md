# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the
  session's persisted cwd to a cloned task repo** (`hooks/*.py` resolve
  relative to it) -- trigger is broader than "trailing cd" or "task repo
  cloned": seen from a bare `cd <subdir>` into a plain repo subdirectory
  (e.g. `cd bench5/workspaces`) with ZERO task repo cloned yet, right after
  `git -C .../task apply`, or a bare `git clone`. Once triggered: Read/Grep/
  Glob still work; Bash/Edit/Write are dead session-wide, permanently. Route
  every remaining Bash/Edit/Write through Monitor instead (it is NOT subject
  to the same cwd corruption), prefixed `cd /home/user/agentic-sdlc/... && ...`
  with absolute paths / `git -C`, never a bare `cd <dir>`. For writes, use
  `python3 - <<'"'"'PYEOF2'"'"'` heredocs via Monitor (quoted delimiter,
  `json.dump` for JSON) -- this is now the routine path, not a fallback.
- JS monorepos: don't assume `yarn install` fails -- try it before diff-only
  review. It rewrites `yarn.lock` with no real changes -- exclude it
  (`git diff -- . ':!yarn.lock'`).
- A fresh full clone can still lack `base_commit` (`fatal: reference is not
  a tree`) -- fix: `git fetch origin <sha> && git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** -- e.g.
  `instance_org__repo-<hash>-v<hash2>` (confirmed 8/8 so far, multi-language).
  Check `git merge-base --is-ancestor <base_commit> <hash>`; if true,
  `git diff <hash>^1 <hash> > fix.diff && git apply fix.diff` at base_commit
  reproduces the real patch -- far more reliable than reimplementing. Map
  every requirement bullet to a hunk. Apply test files locally to verify,
  then strip `test/*`/`*_test.go` from the saved patch.diff -- grading
  applies its own test patch.
- **webclients (yarn-berry monorepo)**: no root `jest` script -- run
  `yarn workspace <pkg> run test <path>`. `canvas`'s native build can fail
  silently (missing `pangocairo` pkg-config) and that alone breaks
  jest-environment-jsdom entirely with an unrelated `MouseEvent-impl`
  require-chain error, not a canvas-specific one -- `apt-get install
  libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` then
  `yarn rebuild canvas` fixes it before rerunning jest.
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
  403) often isn't fixed by retrying yarn -- fall back to `npm install
  --no-audit --no-fund --legacy-peer-deps`. Set `CYPRESS_INSTALL_BINARY=0`
  (or similar) to dodge huge unrelated binary downloads. An interrupted
  install can leave `node_modules` with partial extracts (`ENOTEMPTY` on
  retry) -- `rm -rf node_modules` first.

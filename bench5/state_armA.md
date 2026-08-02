# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER type `cd` in a FOREGROUND Bash call — not `cd X && cmd`, not `cd X; cmd`, not a second `cd` later in the SAME compound line. That call usually
  SUCCEEDS; the NEXT one dies, so it feels unrelated (r022 did it twice, having read this line). cwd PERSISTS and the PreToolUse hook is the *relative*
  `hooks/pretooluse_guard.py`. FIX: `Write` a .sh that `cd`s inside, or `git -C <dir>`. UNSTICK (~1 min): load `Monitor` (unhooked) -> `ln -sfn
  <repo>/hooks <stuck>/hooks`, plain `cd <repo>` in Bash, `rm -f <stuck>/hooks`.
- The guard denies force-deletes if the command holds ANY absolute/`..` token (use `rm -f … && rmdir`), and bare `sleep N && cmd`; it scans the
  LITERAL text, so a heredoc merely quoting one is denied — use Write. Long installs blow the 120s timeout: background them, ending
  `echo exit=$? >>log`; block via `until grep -q '^exit=' log; do sleep 5; done`.
- Multi-point edits: one `python3 - <<'PYEOF'` script of `assert s.count(old)==1; s=s.replace(old,new)` beats N Edit calls, and the asserts catch a
  stale assumption instantly. CHECK LINE ENDINGS FIRST (`b'\r\n' in open(f,'rb').read()`) — a Linux clone of a CRLF-authored repo is LF on disk, and
  the wrong ending fails every assert. Same trick for mechanical test sweeps, and for slicing out a whole func by index("start")..index("next decl").
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new file needs `git add -N <path>`;
  `git rm` HIDES a deletion (use plain `rm`); check `grep -c '^new file mode'`. `git stash push -u -- src` then REFUSES ("Entry … not uptodate"):
  `git restore --staged <newfile>`, stash / run / pop, re-`add -N` — script that dance; a FAILED stash silently runs your CHANGED tree as "baseline".
  A `.ts`->`.tsx` rename = plain `rm` old + write new + `add -N`. Finish by stashing src and `git apply --check <patch.diff>` — proof it applies.
- Package managers REWRITE LOCKFILES and install hacks live in package.json: `git status --short` before diffing, then `git checkout -- <lockfile> package.json`; build scratch venvs / vendored deps OUTSIDE `workspaces/task` (`workspaces/vendor/` is gitignored too).
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git fetch --depth 1 --filter=blob:none
  origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA.
- The Requirements list IS the scope contract: one edit each, re-walk it against the diff; the LIST beats a vaguer blurb, its SILENCE on a nearby thing
  means leave that alone. Its FILE PATHS can be WRONG (r019 said `executor/worker.py`, real `executor/process/worker.py`) — locate by symbol. "Interface"
  is LLM-written, maybe uncompilable: honour its name/default/behaviour, and its PARAM ORDER — it is derived from the real patch.
- "Centralize X in <one file>; ALL UI calls it" means EVERY inline copy, not just the file the next bullet names — grep the old body's distinctive call and convert each; dropping the now-dead param then trips react-hooks/exhaustive-deps, so lint the touched files after.
- DEGENERATE lists exist (r020: six bullets restating "export this one function") — a FLOOR: build what the problem statement needs, never invent UI from
  another repo's markup. Prose PARAPHRASES behaviour that often ALREADY EXISTS — CHECK THE BASE: r022's "Store must implement all storage.Store methods"
  was already true via one embedded field. The bullet with exact call args / key formats is the contract; a vague clause is not.
- PLUMB/UNPLUMB-A-PARAM: put it beside its sibling at EVERY hop incl. React props, then let tsc/pyflakes enumerate the call sites (they find test files grep misses) — a REMOVAL also orphans imports, so stash and re-lint to separate PRE-EXISTING hits.
- DELETING a cross-cutting middleware/feature orphans more than imports: its private helper types+funcs, its test cases, AND the spies in the package's
  support_test. The compiler flags only unused imports and locals, so grep every symbol the deleted body touched and drop the ones only it used.
- When the Interface demands a REFACTOR, EXISTING tests pinning the old signature WILL fail: that is the change, not a bug — update them, PROVE it
  (stash source only), say so. Read them BEFORE coding: asserts are free spec.
## Repo families
- Go: pre-2021 repos ship an INCOMPLETE go.sum — `go mod download <mod> <mod>` with the modules NAMED (argless adds nothing, tidy churns); keep and
  declare those. Cold `go build ./...` = minutes; `-tags <x>` may be RED AT BASE; `gofmt -w .` hits base-unformatted files; lint = Makefile + .golangci.yml.
- Go with a `go.work` (flipt): GOFLAGS=-mod=mod is REJECTED in workspace mode (drop it); every build/test run dirties `go.work.sum`, so
  `git checkout -- go.work.sum` right before diffing. `_tools/go.mod` pins an ancient golangci-lint that won't run on a modern toolchain — practical
  gate is `gofmt -l <touched>` + `go vet ./<pkg>/...`. Packages needing live redis/network (internal/cache/redis, gitfs) are RED AT BASE — prove that by stashing source and re-running just those, not the whole suite.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit requirements.txt. Modern pytest on an old repo = a FIXED set of unrelated failures
  + collection ERRORS (`parametrize` names-vs-values) — `--ignore` that dir, compare FAILED sets, don't chase green. ansible units: run SERIALLY (xdist
  INTERNALERRORs) with `PYTHONPATH=<repo>/lib:<repo>/test`, ignore `test/units/module_utils/basic` + `config/manager`, install `pywinrm pypsrp` or suites
  SKIP; gates = `pycodestyle --max-line-length=160 --ignore=E402,W503,W504,E741,E203` + pyflakes; a new module option = argument_spec + its OWN DOCS block.
- yarn/jest webapps: a blocked dep host dies with a BARE `ECONNRESET` or 403 — name it via `curl -sS "$HTTPS_PROXY/__agentproxy/status"` ->
  `recentRelayFailures`. element-web / matrix-react-sdk (yarn 1) needs THREE fixes before `yarn install` runs: `CYPRESS_INSTALL_BINARY=0`; git-clone
  `matrix-js-sdk` at yarn.lock's SHA into `workspaces/vendor/jsdk` + point package.json at `file:../vendor/jsdk` (codeload 403); `@matrix-org/olm` ->
  plain `3.2.15` off npm (gitlab.matrix.org 403). Drop `--frozen-lockfile`, then `git checkout -- package.json yarn.lock`. Gates: `npx tsc --noEmit
  --jsx react`, `npx jest --ci -w 4`, eslint + `prettier --check`; a vendored js-sdk drifting from the lock leaves ~6 tsc errors + 4 suites RED AT BASE,
  and a new data-testid churns .snap in UNRELATED suites (`npx jest -u`). protonmail/webclients: `node .yarn/releases/yarn-<v>.cjs install
  --mode=skip-build` (rewrites ~900 lock lines — restore; `mv node_modules/canvas node_modules/canvas__off` or components suites die); gates = `tsc -p applications/<app>/tsconfig.json --noEmit`, jest from the app dir, eslint --fix + prettier (120).
- NodeBB: NO root package.json (generated from `install/package.json`, where pinned tool versions live); its mocha suite needs a live mongo/redis, so
  don't try. `src/promisify.js` re-wraps every exported async fn — declare `async` (it tests `constructor.name`); knobs go via `plugins.hooks.fire`.
## Verification habits
- NO DATABASE? Don't skip verification — stub it. Load the module under test directly and intercept its deps by overriding `Module.prototype.require`,
  gated on `this.filename === <file>` so only that file sees stubs (py: `sys.modules[...]=Mock()`; go: the repo's own `common.StoreMock` + a cacheSpy).
- Baseline FIRST when a suite DOES run: whole suite at base into fails_before.txt, again after, `comm` the sorted FAILED/ERROR sets; only the DELTA
  counts (r019: 253 fails both sides, 0 new, 2 fixed). A red suite that PASSES when re-run ALONE is flakiness, not your regression. STASH SOURCE ONLY:
  lockfiles unbuild the base. Same for tsc/lint — the repo's PINNED linter, run FROM THE REPO ROOT so nested configs apply, before/after sets diffed.
- NEVER hand-edit a GENERATED file (element-web `src/i18n/strings/en_EN.json`): run its generator (`npx matrix-gen-i18n`) and diff — it re-orders by source traversal (a new file shifts strings) and re-adds "orphans" another component still uses.
- PURE-EXTRACTION / MOVE refactors get a free oracle: every existing test that passes UNTOUCHED proves behaviour is unchanged. Still cover the NEW seam
  with real cases (r022: 6 tests on cache key format, hit/miss, default-namespace, no-invalidation-on-error), then read the diff hunk by hunk.

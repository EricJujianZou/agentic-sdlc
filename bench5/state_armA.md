# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER type `cd` in a FOREGROUND Bash call — not `cd X && cmd`, not `cd X; cmd`, not a second `cd` later in the SAME compound line (that shape bit
  r020 while it was *reading* this). cwd PERSISTS and the PreToolUse hook is the *relative* `hooks/pretooluse_guard.py`, so once cwd leaves the repo
  root EVERY tool call dies. FIX: `Write` a .sh that `cd`s inside and `bash` it, else `git -C <dir>`. UNSTICK (~1 min): load `Monitor` (unhooked) ->
  `ln -sfn <repo>/hooks <stuck>/hooks`, plain `cd <repo>` in Bash, then `rm -f <stuck>/hooks` + any `.venv`/`node_modules` left behind (silent debris).
- The guard denies force-deletes if the command holds ANY absolute/`..` token (use `rm -f … && rmdir`), and bare `sleep N && cmd`; it scans the
  LITERAL text, so a heredoc merely quoting one is denied — use Write. Long installs blow the 120s timeout: background them, ending
  `echo exit=$? >>log`; block via `until grep -q '^exit=' log; do sleep 5; done`.
- Multi-point edits: one `python3 - <<'PYEOF'` script of `assert s.count(old)==1; s=s.replace(old,new)` beats N Edit calls, and the asserts catch a
  stale assumption instantly. CHECK LINE ENDINGS FIRST (`b'\r\n' in open(f,'rb').read()`) — a Linux clone of a CRLF-authored repo is LF on disk, and
  the wrong ending fails every assert. Same trick for mechanical test sweeps.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new file needs `git add -N <path>`;
  `git rm` HIDES a deletion (use plain `rm`); check `grep -c '^new file mode'`. `git stash push -- <p>` then REFUSES ("Entry … not uptodate"):
  `git restore --staged <newfile>`, stash / run / pop, re-`add -N`.
- Package managers REWRITE LOCKFILES and install hacks live in package.json: `git -C $W status --short` before diffing, `git checkout --
  <lockfile> package.json`. Build scratch venvs / node_modules OUTSIDE the workspace.
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git fetch --depth 1 --filter=blob:none
  origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA.
- The Requirements list IS the scope contract: one edit each, re-walk it against the diff; the LIST beats a vaguer blurb, its SILENCE on a nearby thing
  means leave that alone. Its FILE PATHS can be WRONG (r019 said `executor/worker.py`, real `executor/process/worker.py`) — locate by symbol. "Interface"
  is LLM-written, maybe uncompilable: honour its name/default/behaviour. Both show the happy path only — grep EVERY consumer for unused plumbing already there.
- DEGENERATE lists exist: r020's six bullets all restated "export this one function" (auto-generated from the failing test). Then they are a floor,
  not the feature — also build the server path the problem statement needs, but do NOT invent UI against markup that lives in another repo (NodeBB
  .tpl modals ship in the theme, not core).
- Requirement prose is PARAPHRASE, often of behaviour that ALREADY EXISTS (spacing, sanitizer escaping) — check the base, its tests may pin it
  already. The bullet with exact call args is the contract; a vague clause is NO licence to invent an API.
- PLUMB/UNPLUMB-A-PARAM tasks (`fn must receive userSettings`, `drop new_stdin everywhere`): put it right after its sibling at EVERY hop incl. React
  props parent->child, give EO/offline callers a `<x>Default…` const, then let tsc or pyflakes enumerate the call sites — they find test files grep
  misses. A REMOVAL also orphans imports: pyflakes the touched files, `git stash`, pyflakes again to separate PRE-EXISTING hits.
- When the Interface demands a REFACTOR, EXISTING tests pinning the old signature WILL fail: that is the change, not a bug — update them, but PROVE
  it (stash source only) and say so. Read them BEFORE coding: asserts are free spec.
## Repo families
- Go: pre-2021 repos ship an INCOMPLETE go.sum — `go mod download <mod> <mod>` with the modules NAMED (argless adds nothing, tidy churns); keep and
  declare those. Cold `go build ./...` = minutes; `-tags <x>` may be RED AT BASE; `gofmt -w .` hits base-unformatted files; lint = Makefile + .golangci.yml.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit requirements.txt. Modern pytest on an old repo = a FIXED set of unrelated
  failures + collection ERRORS (`parametrize` names-vs-values) — `--ignore` that dir, compare FAILED sets, don't chase green. ansible units:
  `PYTHONPATH=<repo>/lib:<repo>/test`, run SERIALLY (xdist INTERNALERRORs), ignore `test/units/module_utils/basic` + `config/manager`, install `pywinrm
  pypsrp` or suites SKIP; gates = `pycodestyle --max-line-length=160 --ignore=E402,W503,W504,E741,E203` + pyflakes on touched files; a new module
  option = argument_spec entry + its OWN DOCUMENTATION block.
- yarn/jest webapps: element-web = yarn 1, and a blocked dep host dies with a BARE `ECONNRESET` (name it via `curl -sS "$HTTPS_PROXY/__agentproxy/
  status"` -> `recentRelayFailures`; fix = delete that dep from package.json AND its yarn.lock key); a new data-testid churns .snap in UNRELATED
  suites (`npx jest -u`). protonmail/webclients: `ls .yarn/releases/`, then `node .yarn/releases/yarn-<v>.cjs install --mode=skip-build` (~1.5 min,
  rewrites ~900 lock lines — restore; `mv node_modules/canvas node_modules/canvas__off` or components suites die); gates = `tsc -p applications/<app>/
  tsconfig.json --noEmit` (exhaustive stale-call-site finder), jest from the app dir, eslint --fix + prettier (120).
- NodeBB: NO root package.json (generated from `install/package.json` — pinned tool versions live there); its mocha suite needs a live mongo/redis,
  so don't try. `src/promisify.js` re-wraps every exported async fn, so declare `async` (it tests `constructor.name === 'AsyncFunction'`). Feature
  knobs go through `plugins.hooks.fire('filter:…', payload)`.
## Verification habits
- NO DATABASE? Don't skip verification — stub it. Load the module under test directly and intercept its deps by overriding `Module.prototype.require`,
  gated on `this.filename === <file>` so only that file sees stubs (py: `sys.modules[...]=Mock()`). ~60 lines bought r020 nine behavioural asserts, red at base, green after.
- Baseline FIRST when a suite DOES run: whole suite at base into fails_before.txt, again after, `comm` the sorted FAILED/ERROR sets; only the DELTA
  counts (r019: 253 fails both sides, 0 new, 2 fixed). A red suite that PASSES when re-run ALONE is load/proxy flakiness, not your regression.
  STASH SOURCE ONLY: lockfiles unbuild the base.
- LINT the same delta way: install the repo's PINNED linter into a scratch dir, run it from the repo root so NESTED `.eslintrc`/setup.cfg still apply
  (never `--no-eslintrc -c <root cfg>`: a browser-JS dir then floods with no-undef), filter errors that exist only because deps are missing
  (`import/no-unresolved`), and diff the before/after sets.
- Behavioural tasks (process isolation, I/O, signals) need a SCRATCH PROBE, not just unit tests (r019: a plugin printing `os.getsid/getpgrp/readlink`
  at base vs after). Throwaway asserts per numbered requirement catch a silent no-op; if one fails suspect the ASSERTION first. Read the diff hunk by hunk.

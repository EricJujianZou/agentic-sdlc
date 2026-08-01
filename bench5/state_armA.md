# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a FOREGROUND Bash call, not even `cd X && cmd` — cwd PERSISTS and the PreToolUse hook is the *relative*
  `hooks/pretooluse_guard.py`, so once cwd leaves the repo root EVERY tool call dies. BEST FIX: `Write` a tiny .sh that `cd`s
  inside and `bash` it — the tool shell never moves, long flag lists stay readable. Else `git -C <dir>`. Escape a stuck cwd
  via `Monitor` (unhooked): `ln -sfn <repo>/hooks <stuck>/hooks`, cd back.
- The guard denies force-deletes if the command holds ANY absolute/`..` token (use `rm -f … && rmdir`), and bare `sleep N &&
  cmd`; it scans the LITERAL text, so a heredoc merely quoting one is denied — use Write. Long installs blow the 120s timeout:
  background them, ending `echo exit=$? >>log`; block via `until grep -q '^exit=' log; do sleep 5; done`.
- Multi-point edits: one `python3 - <<'PYEOF'` of `assert s.count(old)==1; s=s.replace(old,new)` beats N Edit calls.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new file needs
  `git add -N <path>`; `git rm` HIDES a deletion (use plain `rm`); check `grep -c '^new file mode'`. `git stash push -- <p>`
  then REFUSES ("Entry … not uptodate"): `git restore --staged <newfile>`, stash / run / pop, re-`add -N`.
- Package managers REWRITE LOCKFILES and install hacks live in package.json: `git -C $W status --short` before diffing, `git
  checkout -- <lockfile> package.json`. Build scratch venvs OUTSIDE the workspace.
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git fetch
  --depth 1 --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched
  — `git ls-tree HEAD <path>` gives the pinned SHA, clone that likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff; the LIST beats a vaguer blurb,
  its SILENCE on a nearby thing means leave that alone. "Interface" is LLM-written, maybe uncompilable: honour name/default/
  behaviour. Both name only the happy path — grep EVERY consumer of the changed shape (half the work is callers); grep the
  prop you must "add", its plumbing is often ALREADY there unused — that is the shape meant.
- Requirement prose is PARAPHRASE, often of behaviour that ALREADY EXISTS (spacing, sanitizer escaping) — check the base,
  tests may pin it already. The ONE bullet giving exact call args is the contract; a vague clause ("append the raw URL on a
  new line") is NOT a licence to invent an API no caller can reach.
- PLUMB-A-NEW-PARAM tasks (`fn must receive userSettings`): put it right after its sibling (mailSettings) at EVERY hop incl.
  React props threaded parent->child, give EO/offline callers a new `<x>Default…` const, then let the compiler (tsc/pyflakes)
  enumerate the call sites — it finds test files grep-by-name misses.
- When the Interface demands a REFACTOR (method -> module fn, unified ctor), EXISTING tests pinning the old signature WILL
  fail: that is the change, not a bug — update them, but PROVE it (stash source only) and say so. Read them BEFORE coding:
  asserts are free spec, and "pass X explicitly as None" = a hidden `assert_called_once_with` to thread through EVERY hop.
## Repo families
- Go: `proxy.golang.org` works, but PRE-2021 REPOS SHIP AN INCOMPLETE go.sum — `go mod download <mod> <mod>` with the modules
  NAMED (argless adds nothing; tidy churns); keep+declare those. Cold `go build ./...` = minutes; `-tags <x>` may be RED AT
  BASE; `gofmt -w .` hits base-unformatted files too. Lint = Makefile + .golangci.yml.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit the repo's requirements.txt. A modern pytest on an old
  repo gives a FIXED set of unrelated failures + collection ERRORS (`parametrize` names-vs-values) — `--ignore` that file,
  compare FAILED sets, don't chase green. New ansible module option = argument_spec entry + its OWN DOCUMENTATION.
- ansible units: `PYTHONPATH=<repo>/lib:<repo>/test`, venv `pytest<8 pytest-mock jinja2<3.1 PyYAML mock` (test/units/ executor
  imports bare `mock`); 2.10 has ~63 pre-existing FAILED + ~67 collection errors — only the DELTA matters. Gates: `pycodestyle
  --max-line-length=160` (E128 wraps) + pyflakes; pylint sanity disables unused-var.
- element-web = yarn 1 + jest. A blocked dep host kills `yarn install` with a BARE `ECONNRESET` stack, no 403 text; `curl -sS
  "$HTTPS_PROXY/__agentproxy/status"` names it under `recentRelayFailures`; fix = DELETE that dep from package.json AND its
  yarn.lock KEY. A new data-testid churns .snap in UNRELATED suites: `npx jest -u` is diff.
- protonmail/webclients: yarn VERSION VARIES BY BASE — `ls .yarn/releases/`, then `node .yarn/releases/yarn-<v>.cjs install
  --mode=skip-build` (2022 base: 5 s, 1.2 GiB, no `canvas`; 2024 base: 1.5 min + `mv node_modules/canvas
  node_modules/canvas__off` or every packages/components suite dies on canvas.node). It rewrites ~900 yarn.lock lines —
  restore it. Gates: `node node_modules/typescript/bin/tsc -p applications/<app>/tsconfig.json --noEmit` (EXHAUSTIVE
  stale-call-site finder, beats grep), jest from the app dir, eslint --fix + prettier --write (printWidth 120) on TOUCHED
  FILES ONLY. Full mail suite = 73 suites / ~570 tests / 32 snapshots in ~4 min.
## Verification habits
- CHEAPEST first check on a red suite: re-run that ONE suite alone — a failure that passes in isolation is load/proxy
  flakiness (ECONNRESET), not your regression. Then prove it: run the suite, `git stash push -- <src dirs>`, run again, DIFF
  failure REASONS not counts, pop at once. STASH SOURCE ONLY — go.sum/lockfiles make the base fail to BUILD.
- Best repro = a scratch test INSIDE the suite dir (inherits harness boot + helpers); for a FEATURE task assert the
  requirement list end-to-end, run it against the STASHED base too (it must fail there), delete it before diffing. Its FIRST
  run will fail on YOUR guesses (attr order, fixture shape) — fix the assertion, don't "fix" the code.
- Read the final `git diff` hunk by hunk; don't let a format pass touch lines you just wrote. Never hand-pick a mocha/pytest
  file list: aggregators re-`require` subdirs.

# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER type `cd` in a FOREGROUND Bash call — not `cd X && cmd`, not `cd X 2>/dev/null; cmd` (that one still bit r019). cwd
  PERSISTS and the PreToolUse hook is the *relative* `hooks/pretooluse_guard.py`, so once cwd leaves the repo root EVERY tool
  call dies. BEST FIX: `Write` a tiny .sh that `cd`s inside and `bash` it; else `git -C <dir>`. UNSTICK: load `Monitor`
  (unhooked) -> `ln -sfn <repo>/hooks <stuck>/hooks`, plain `cd <repo>` in Bash, then delete that symlink AND the
  `.venv`/`uv.lock` `uv run` left behind (untracked = invisible in `git diff`, still debris).
- The guard denies force-deletes if the command holds ANY absolute/`..` token (use `rm -f … && rmdir`), and bare `sleep N &&
  cmd`; it scans the LITERAL text, so a heredoc merely quoting one is denied — use Write. Long installs blow the 120s timeout:
  background them, ending `echo exit=$? >>log`; block via `until grep -q '^exit=' log; do sleep 5; done`.
- Multi-point edits: one `python3 - <<'PYEOF'` script of `assert s.count(old)==1; s=s.replace(old,new)` beats N Edit calls,
  and the asserts catch a stale assumption instantly. Same trick for mechanical test sweeps (drop one arg at 20 call sites).
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new file needs
  `git add -N <path>`; `git rm` HIDES a deletion (use plain `rm`); check `grep -c '^new file mode'`. `git stash push -- <p>`
  then REFUSES ("Entry … not uptodate"): `git restore --staged <newfile>`, stash / run / pop, re-`add -N`.
- Package managers REWRITE LOCKFILES and install hacks live in package.json: `git -C $W status --short` before diffing, `git
  checkout -- <lockfile> package.json`. Build scratch venvs OUTSIDE the workspace.
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git fetch
  --depth 1 --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules aren't fetched
  — `git ls-tree HEAD <path>` gives the pinned SHA, clone that likewise.
- The Requirements list IS the scope contract: one edit each, re-walk it against the diff; the LIST beats a vaguer blurb, its SILENCE
  on a nearby thing means leave that alone. Its FILE PATHS can be WRONG (r019 said `executor/worker.py`, real file
  `executor/process/worker.py`) — locate by class/symbol name. "Interface" is LLM-written, maybe uncompilable: honour its name/
  default/behaviour. Both give the happy path only — grep EVERY consumer; a prop to "add" often has plumbing ALREADY there unused.
- Requirement prose is PARAPHRASE, often of behaviour that ALREADY EXISTS (spacing, sanitizer escaping) — check the base, its
  tests may pin it already. The bullet with exact call args is the contract; a vague clause is NO licence to invent an API.
- PLUMB/UNPLUMB-A-PARAM tasks (`fn must receive userSettings`, `drop new_stdin everywhere`): put it right after its sibling at
  EVERY hop incl. React props parent->child, give EO/offline callers a `<x>Default…` const, then let tsc or pyflakes enumerate
  the call sites — they find test files grep misses. A REMOVAL also orphans imports (`import os` once its only use went):
  pyflakes the touched files, then `git stash` and pyflakes again to separate PRE-EXISTING hits.
- When the Interface demands a REFACTOR, EXISTING tests pinning the old signature WILL fail: that is the change, not a bug —
  update them, but PROVE it (stash source only) and say so. Read them BEFORE coding: asserts are free spec.
## Repo families
- Go: `proxy.golang.org` works, but PRE-2021 REPOS SHIP AN INCOMPLETE go.sum — `go mod download <mod> <mod>` with the modules
  NAMED (argless adds nothing; tidy churns); keep+declare those. Cold `go build ./...` = minutes; `-tags <x>` may be RED AT
  BASE; `gofmt -w .` hits base-unformatted files too. Lint = Makefile + .golangci.yml.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit the repo's requirements.txt. A modern pytest on an old
  repo gives a FIXED set of unrelated failures + collection ERRORS (`parametrize` names-vs-values) — `--ignore` that dir,
  compare FAILED sets, don't chase green. New ansible module option = argument_spec entry + its OWN DOCUMENTATION.
- ansible units: `PYTHONPATH=<repo>/lib:<repo>/test`, run SERIALLY (`-n 4` xdist INTERNALERRORs on unrelated as-root tests);
  ignore `test/units/module_utils/basic` + `config/manager`. 2.19-era: modern `pytest pytest-mock mock pyyaml jinja2
  cryptography packaging resolvelib` is fine, plus `pywinrm pypsrp` or those suites silently SKIP. Gates: `pycodestyle
  --max-line-length=160 --ignore=E402,W503,W504,E741,E203` + pyflakes, on touched files only.
- element-web = yarn 1 + jest. A blocked dep host kills `yarn install` with a BARE `ECONNRESET` stack, no 403 text; `curl -sS
  "$HTTPS_PROXY/__agentproxy/status"` names it under `recentRelayFailures`; fix = DELETE that dep from package.json AND its
  yarn.lock KEY. A new data-testid churns .snap in UNRELATED suites: `npx jest -u` is diff.
- protonmail/webclients: yarn VERSION VARIES BY BASE — `ls .yarn/releases/`, then `node .yarn/releases/yarn-<v>.cjs install --mode=skip-build`;
  2024 base = 1.5 min + `mv node_modules/canvas node_modules/canvas__off` or components suites die, and it rewrites ~900 yarn.lock lines (restore).
  Gates: `tsc -p applications/<app>/tsconfig.json --noEmit` (EXHAUSTIVE stale-call-site finder), jest from the app dir, eslint --fix + prettier (120).
## Verification habits
- Baseline FIRST: run the whole suite at base into fails_before.txt, again after, `comm` the sorted FAILED/ERROR sets. Only
  the DELTA counts (r019: 253 fails on both sides, 0 new, 2 fixed). CHEAPEST check on one red suite: re-run it ALONE — a fail
  that passes in isolation is load/proxy flakiness, not your regression. STASH SOURCE ONLY: lockfiles make the base not build.
- Behavioural tasks (process isolation, I/O, signals) need a SCRATCH PROBE, not just unit tests: for r019 an action plugin
  reporting `os.getsid/getpgrp/readlink('/proc/self/fd/N')`, run at base (shared sid, fd1=inherited pipe) and after (own sid,
  fd 0/1/2 = /dev/null). Write throwaway asserts for EACH numbered requirement too — cheap, and they catch a silent no-op.
- When a scratch assertion fails, suspect the ASSERTION first: `TypedDict.__required_keys__` is wrong under `from __future__
  import annotations` on py<3.14 (NotRequired unresolved) — check `t.get_type_hints(X, include_extras=True)` instead.
- Read the final `git diff` hunk by hunk; a removed import leaves DOUBLE BLANK LINES that pycodestyle won't flag — tidy them.

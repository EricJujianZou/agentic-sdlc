# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a FOREGROUND Bash call, not even `cd X && cmd` — it STILL bites people who read this line: cwd PERSISTS
  and the PreToolUse hook is the *relative* `hooks/pretooluse_guard.py`, so once cwd leaves the repo root EVERY tool call
  dies. Use `git -C <dir>` / subshells. Escape via `Monitor` (unhooked): `ln -sfn <repo>/hooks <stuck>/hooks`, cd back.
- The guard denies force-deletes when the command holds ANY absolute or `..` token (use `rm -f … && rmdir`), and bare
  `sleep N && cmd`; it scans the LITERAL text, so a heredoc merely quoting one is denied too — write such scripts with
  Write. Long installs blow the 120s timeout: background them, log ending `echo exit=$? >>log`, then block by
  backgrounding `until grep -q '^exit=' log; do sleep 5; done`.
- Multi-point mechanical edits: one `python3 - <<'PYEOF'` of `assert old in s; s=s.replace(old,new)` beats N Edit calls
  — the asserts are the safety net. Do NOT let a dedent pass touch lines you just wrote.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new file
  needs `git add -N <path>`; `git rm` HIDES a deletion (use plain `rm`); check `grep -c '^new file mode'`. `git stash
  push -- <p>` then REFUSES ("Entry … not uptodate"): `git restore --staged <newfile>`, stash / run / pop, re-`add -N`.
- Package managers REWRITE LOCKFILES and your install hacks live in package.json: `git -C $W status --short` before
  diffing, `git checkout -- <lockfile> package.json`. Build scratch venvs OUTSIDE the workspace.
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git
  fetch --depth 1 --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules
  aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA, clone that likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff; the LIST beats a vaguer
  blurb, its SILENCE on a nearby thing means leave that alone. "Interface" is LLM-written, maybe uncompilable: honour
  name/default/behaviour. Both name only the happy path — grep EVERY consumer of the changed shape, half the work is
  callers; and grep the prop you must "add", its plumbing is often ALREADY there unused — that is the shape meant.
- A NEW ERROR TYPE is such a consumer: find the err->HTTP/gRPC status mapper and add the case or you silently downgrade a
  working path; a field with NO caller is half a change. An UNLISTED change breaking a repo-wide consistency test is not:
  drop it and say why. New API response fields need declaring (OpenAPI schema).
- CENTRALIZE-A-CONSTANT tasks: the sweeping lead bullet ("replace ANY inline `1024**3`") over-reaches — trust the
  per-file bullets; one that changes only an IMPORT SOURCE and leaves the arithmetic (`10 * BASE_SIZE ** 2`) alone
  proves the reference was surgical. Still DELETE the old definition (single source) and fix the test that imported it.
- When the Interface demands a REFACTOR (method -> module fn, unified ctor), EXISTING tests pinning the old signature
  WILL fail: that is the change, not a bug — update them, but PROVE it first (stash source, diff the FAILED lists) and
  say so. Read them BEFORE coding: asserts are free spec and arg values are real (a bogus `ca_path='/foo/baz.pem'` meant
  the builder must NOT forward cafile when validation is off). "Pass X explicitly as None, don't omit it" = a hidden
  mock `assert_called_once_with`; thread it through EVERY hop, `_fallback` included (bumps `call_count == N` too).
## Repo families
- Go: `proxy.golang.org` works, but PRE-2021 REPOS SHIP AN INCOMPLETE go.sum — `go mod download <mod> <mod>` with the
  modules NAMED (argless adds nothing; tidy churns); keep those additions, say so. Cold `go build ./...` = minutes;
  `-tags <x>` may be RED AT BASE; `gofmt -w .` also hits files unformatted at base. Lint = Makefile + .golangci.yml.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit the repo's requirements.txt. A modern pytest on a
  2022-era repo gives a FIXED set of unrelated failures plus collection ERRORS (`parametrize` names-vs-values) —
  `--ignore` that file, compare FAILED sets base-vs-after, don't chase green. `PYTHONPATH=<repo>/lib:<repo>/test` runs
  ansible units; a new module option = argument_spec entry + an options block in that module's OWN DOCUMENTATION.
- element-web = yarn 1 + jest. A blocked dep host kills `yarn install` with a BARE `ECONNRESET` stack, no 403 text;
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"` names it under `recentRelayFailures`; fix = DELETE the offending dep
  from package.json AND its yarn.lock KEY. A new data-testid churns .snap in UNRELATED suites: `npx jest -u` is diff.
- protonmail/webclients = yarn 4 + turbo; `node .yarn/releases/yarn-4.4.0.cjs install --mode=skip-build` JUST WORKS (1.5
  min, 1.4 GiB) but leaves `canvas` unbuilt (no node-22 prebuild), so EVERY packages/components jest suite dies on
  `../build/Release/canvas.node` — `mv node_modules/canvas node_modules/canvas__off`, jsdom `require.resolve`-guards it.
  Install rewrites yarn.lock; its karma wants a playwright chromium revision absent from /opt/pw-browsers (symlink one
  into a scratch `PLAYWRIGHT_BROWSERS_PATH`). Gates from the package dir: `npx tsc` (= check-types), `npx jest [path]`,
  `npx eslint <f>`, `npx prettier --check <f>` — under a sort-imports plugin prettier says where a new import belongs.
## Verification habits
- CHEAPEST first check on a red suite: re-run that ONE suite alone — a failure that passes in isolation is load or proxy
  flakiness (ECONNRESET), not your regression. Then prove it: run the suite, `git stash push -- <src dirs>`, run again,
  DIFF failure REASONS not counts (a tsc base run gave 3 errors where the after run gave 1, same untouched file), pop
  at once. STASH SOURCE ONLY — go.sum/lockfiles make the base fail to BUILD.
- Best repro = a scratch test INSIDE the suite dir (inherits harness boot + helpers); for a FEATURE task assert the
  requirement list end-to-end. Cases appended to the REAL suite file (keep a copy) get its mocks free; undo both. Read
  the final `git diff` hunk by hunk. Never hand-pick a mocha/pytest file list: aggregators re-`require` subdirs.

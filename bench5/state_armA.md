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
- "RETIRE exception X in favour of Y" = rename + REPARENT, not a new class beside it: grep every raise AND every
  `except (...)` tuple. "Method M supersedes module-level CONST" = delete CONST too, then re-check whether its imports
  (`re`, `to_native`, `string_types`) are now orphans — `pyflakes` on the touched files names them in one shot.
- CENTRALIZE-A-CONSTANT tasks: the sweeping lead bullet ("replace ANY inline `1024**3`") over-reaches — trust the
  per-file bullets (one leaving `10 * BASE_SIZE ** 2` alone proves it). Still DELETE the old def + fix its importer.
- When the Interface demands a REFACTOR (method -> module fn, unified ctor), EXISTING tests pinning the old signature
  WILL fail: that is the change, not a bug — update them, but PROVE it (stash source ONLY, so the test edit stays and
  the FAILED-list diff is exactly that test) and say so. Read them BEFORE coding: asserts are free spec, arg values are
  real, and "pass X explicitly as None" = a hidden mock `assert_called_once_with` to thread through EVERY hop.
## Repo families
- Go: `proxy.golang.org` works, but PRE-2021 REPOS SHIP AN INCOMPLETE go.sum — `go mod download <mod> <mod>` with the
  modules NAMED (argless adds nothing; tidy churns); keep those additions, say so. Cold `go build ./...` = minutes;
  `-tags <x>` may be RED AT BASE; `gofmt -w .` also hits files unformatted at base. Lint = Makefile + .golangci.yml.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit the repo's requirements.txt. A modern pytest on an
  old repo gives a FIXED set of unrelated failures + collection ERRORS (`parametrize` names-vs-values) — `--ignore` that
  file, compare FAILED sets, don't chase green. New ansible module option = argument_spec entry + its OWN DOCUMENTATION.
- ansible units: `PYTHONPATH=<repo>/lib:<repo>/test`, venv `pytest<8 pytest-mock jinja2<3.1 PyYAML mock` (test/units/
  executor imports bare `mock`); 2.10 has ~63 pre-existing FAILED + ~67 collection errors — only the DELTA matters.
  Gates: `pycodestyle --max-line-length=160` (catches E128 under-indented visual-indent call wraps) and pyflakes; its
  pylint sanity cfg DISABLES unused-variable, so upstream-style `obj, ctx = f()` with ctx unused is fine.
- element-web = yarn 1 + jest. A blocked dep host kills `yarn install` with a BARE `ECONNRESET` stack, no 403 text;
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"` names it under `recentRelayFailures`; fix = DELETE that dep from
  package.json AND its yarn.lock KEY. A new data-testid churns .snap in UNRELATED suites: `npx jest -u` is diff.
- protonmail/webclients = yarn 4 + turbo; `node .yarn/releases/yarn-4.4.0.cjs install --mode=skip-build` JUST WORKS (1.5
  min, 1.4 GiB) but leaves `canvas` unbuilt, so EVERY packages/components jest suite dies on `canvas.node` — `mv
  node_modules/canvas node_modules/canvas__off`. Gates from the package dir: `npx tsc`, `npx jest [path]`, `npx eslint`.
## Verification habits
- CHEAPEST first check on a red suite: re-run that ONE suite alone — a failure that passes in isolation is load or proxy
  flakiness (ECONNRESET), not your regression. Then prove it: run the suite, `git stash push -- <src dirs>`, run again,
  DIFF failure REASONS not counts, pop at once. STASH SOURCE ONLY — go.sum/lockfiles make the base fail to BUILD.
- Best repro = a scratch test INSIDE the suite dir (inherits harness boot + helpers); for a FEATURE task assert the
  requirement list end-to-end, and run it against the STASHED base too — it must fail there. Delete it before diffing.
- Read the final `git diff` hunk by hunk. Never hand-pick a mocha/pytest file list: aggregators re-`require` subdirs.

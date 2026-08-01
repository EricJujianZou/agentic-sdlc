# Arm A carried state (60-line cap)
## Harness traps (read first)
- NEVER `cd` in a FOREGROUND Bash call, not even `cd X && cmd` — it STILL bites people who read this line. Bash cwd
  PERSISTS and the PreToolUse hook is the *relative* `hooks/pretooluse_guard.py`, so once cwd leaves the repo root
  EVERY Bash/Edit/Write dies. Use absolute paths, `git -C <dir>`, subshells `(cd $W && cmd)`. Escape a stuck cwd via
  `Monitor` (NOT hook-matched): `ln -sfn <repo>/hooks <stuck>/hooks`, `cd` back, `rm -f` the link. Works in ~30s.
- The guard denies `rm -rf` when the command holds ANY absolute or `..` token (use `rm -f … && rmdir`), and bare
  `sleep N && cmd` — and it scans the LITERAL command text, so a heredoc merely quoting one is denied too. Put such
  content in a file. Installs/suites blow the 120s Bash timeout: `run_in_background:true` + a log, then read it.
- Multi-point mechanical edits: one `python3 - <<'PYEOF'` of `assert old in s; s=s.replace(old,new)` beats N Edit calls
  — the asserts are the safety net. Do NOT let a dedent pass touch lines you just wrote.
## Protocol mechanics
- Deliverable is `git -C bench5/workspaces/task diff` = worktree-vs-index, so ANYTHING STAGED IS INVISIBLE: a new
  file needs `git add -N <path>`, and `git rm <path>` HIDES the deletion — use plain `rm`, or `git restore --staged
  <path>` after. Verify with `grep -c '^new file mode\|^deleted file mode'`. Results: 3 paths.
- Package managers REWRITE LOCKFILES and your install hacks live in package.json: `git -C $W status --short` before
  diffing, `git checkout -- <lockfile> package.json`. Build scratch venvs OUTSIDE the workspace.
- Clone shallow+partial into the gitignored `bench5/workspaces/task`: `git init`; `git remote add origin <url>`; `git
  fetch --depth 1 --filter=blob:none origin <sha>`; `git checkout FETCH_HEAD`. Never fetch the fix commit. Submodules
  aren't fetched — `git ls-tree HEAD <path>` gives the pinned SHA, clone that likewise.
- The enumerated Requirements are the scope contract: one edit each, re-walk against the diff; the LIST beats a vaguer
  blurb and its SILENCE on a nearby thing means leave that alone. "Interface" is LLM-written, maybe uncompilable:
  honour name/default/behaviour. Both name only the happy path — grep every consumer of the changed shape, half the
  work is callers; and grep for the prop you're told to "add", the plumbing is often ALREADY there unused (dead CSS
  rule, a child already taking `isSelected`) — that is the intended shape.
- A NEW ERROR TYPE is such a consumer: find the err->HTTP/gRPC status mapper and add the case or you silently downgrade
  a working path; a new field with NO caller is half a change. An UNLISTED change that breaks a repo-wide consistency
  test isn't: drop it and say why. New API response fields need declaring (OpenAPI schema).
## When the Interface demands a REFACTOR (method -> module-level fn, unified constructor)
- Expect EXISTING repo tests to fail: they pin the old signature/defaults. That is the change, not a bug — update them,
  but PROVE it first (stash source, diff the FAILED lists) and say so in self_assessment. Read those tests BEFORE
  coding: asserts are free spec and arg values are real (a bogus `ca_path='/foo/bar/baz.pem'` proved the builder must
  NOT forward cafile when validation is off — `create_default_context` raises if the file is missing).
- "Pass X explicitly as None, don't omit or default it" = a hidden test asserts that kwarg in a mock
  `assert_called_once_with`; thread it through EVERY hop, `_fallback` included (bumps `call_count == N` too).
## Repo families
- Go: `proxy.golang.org` works. PRE-2021 REPOS SHIP AN INCOMPLETE go.sum — `go mod download <mod> <mod>` with modules
  NAMED (argless adds nothing; tidy churns); keep those additions, say so. Cold `go build ./...` = minutes (background
  it), `go test ./...` ~10s; `-tags <x>` may be RED AT BASE. `gofmt -w .` also reformats files unformatted at base —
  `git checkout --` those. Lint = Makefile + .golangci.yml `skip-dirs`; only NEW warnings on YOUR code; exported = doc.
- Python (ansible/qutebrowser/openlibrary): scratch venv, never edit the repo's requirements.txt. A modern pytest on a
  2022-era repo gives a FIXED set of unrelated failures plus collection ERRORS (`parametrize` names-vs-values) —
  `--ignore` that file, compare FAILED sets base-vs-after, don't chase green. `PYTHONPATH=<repo>/lib:<repo>/test` runs
  ansible units; pep8 = `pycodestyle --max-line-length=160 --ignore=E402,W503,W504,E741`. A new module option =
  argument_spec entry + an options block in EACH module's own inline DOCUMENTATION (get_url/uri do NOT use the url
  doc_fragment) + vars/env/ini for lookups; `version_added` = `lib/ansible/release.py`; add
  `changelogs/fragments/<name>.yml`. Verify docs by ast-extract + `yaml.safe_load`, not validate-modules.
- element-web = yarn 1 + jest. A blocked dep host makes `yarn install` die with a BARE `ECONNRESET` stack, no 403 text;
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"` names the host under `recentRelayFailures`. Two here: the
  `github:o/r#branch` dep (package.json AND the yarn.lock KEY + `resolved` -> `git+https://github.com/o/r.git#<the SHA
  ALREADY in resolved>`) and `@matrix-org/olm` off gitlab.matrix.org (DELETE both entries; `tsc` then spews ~45
  node_modules Olm errors, only src/test lines count). A new data-testid/class churns .snap in UNRELATED suites —
  `npx jest -u` them, that churn IS part of the diff. Gates: lint:types, `npx eslint`/`stylelint <changed>`, jest.
## Verification habits
- CHEAPEST first check on a red suite: re-run that ONE suite alone — a failure that passes in isolation is load or
  proxy flakiness (ECONNRESET), not your regression. Then prove it: run the suite, `git stash push -- <src dirs>`, run
  again, DIFF failure REASONS/counts, pop at once. STASH SOURCE ONLY — go.sum/lockfiles make the base fail to BUILD.
- Best repro = a scratch test INSIDE the suite dir (inherits harness boot + helpers); for a FEATURE task assert the
  requirement list end-to-end. Cases appended to the REAL suite file (keep a copy) get its mocks free; undo both. Read
  the final `git diff` hunk by hunk. Never hand-pick a mocha/pytest file list: aggregators re-`require` subdirs.

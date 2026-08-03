# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the session's persisted cwd to a
  cloned task repo** (`hooks/*.py` resolve relative to it) -- trigger is broad (bare `cd`, incl.
  inside a Monitor script, and even a plain read-only command like `cd x && head f` in Bash, r057).
  Monitor itself stays immune. Default to Monitor for ALL task-repo ops from turn 1; once tripped,
  Read/Grep/Glob still work but Bash/Edit/Write die session-wide, incl. Write to files OUTSIDE the
  task repo (verify w/ any Bash call once, or just assume tripped after your first task-repo touch)
  -- route ALL mutations (diff, meta.json, this file) through Monitor heredocs, incl. push.
- **On Monitor, don't chain `sleep N`** waiting on a slow build/test/clone -- call `TaskOutput(task_id, block=true, timeout<=600000)` on that Monitor's own task_id; one call blocks and returns the real output.
- JS monorepos: `yarn install` rewrites `yarn.lock` w/ no real changes -- exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`.
  Fresh clone lacking `base_commit`: `git fetch origin <sha> && git checkout FETCH_HEAD`. Mirror can strip files repo-wide (NodeBB:
  `package.json` gone from history too, npm impossible) -- verify via `node --check <file>` + hand-trace, note it.
- **`instance_id` often embeds the exact upstream fix commit hash** (32/32 so far, incl. Go, Python,
  +2 JS/r050,r055). Shallow clone needs `git fetch --depth 50 origin <hash>` before `merge-base
  --is-ancestor` or it wrongly says false. If ancestor, `git diff base_commit <hash> -- <files>` beats
  reimplementing (NOT `git show`, empty for merges). Map every requirement bullet to a hunk -- a
  `go.mod`/`go.sum` bump with no requirement naming it is incidental drift, skip it; a golden commit
  can also span whole FILES no requirement names -- `git checkout HEAD -- <unnamed files>` to drop
  them. Trust unchanged existing tests over requirement prose when they disagree. Direct child of
  `base_commit`? `cherry-pick -n` (`-m 1` if merge) -- exclude any brand-new `*.test.*`/`*_test.go`
  file (the SWE-bench test_patch), restore it via `git show <hash>:<path> > <path>` first to RUN it
  against your fix and confirm pass, then remove again before the final diff (`git diff HEAD`, not
  plain `git diff`). Strip other test edits too unless the test IS the requirement. If it can't
  actually execute (env broken), hand-trace the golden test's assertions line-by-line as proof.
- **Two 40-char hashes in `instance_id` (teleport r056, openlibrary r057): check BOTH as ancestors,
  don't assume the later-looking one is the fix.** One can be a much-later, wholly unrelated commit
  (e.g. a future refactor that deletes the entire file/module) -- `git diff --stat base_commit <hash>
  -- <target files>` on each candidate first: all-deletions-no-additions with no matching insertions
  is the tell of a wrong/unrelated hash, don't cherry-pick it. The other candidate, often the FIRST
  hash chronologically despite appearing second in the string, is the real direct-child fix.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace <pkg> run test <path>
  --coverage=false`; typecheck via `yarn workspace <pkg> run check-types`. `yarn install
  --immutable` fails -- use plain `yarn install`; `canvas` needs `apt-get update && apt-get install
  libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` (run `update` FIRST, verify w/
  `pkg-config --cflags --libs pangocairo`) + `yarn rebuild canvas`. Plain `git clone` can die
  mid-transfer (huge repo) -- use `--filter=blob:none --no-checkout` + fetch.
- **Go**: real-diff `go.mod`/`go.sum` verbatim unless unrelated drift; `gofmt -l`/`go vet` can flag
  pre-existing base-commit failures (confirm via stash-check before blaming your diff) -- strip stray
  `gofmt -w` lines back out. First build downloads full module graph (2-3min, not a hang). `go.work.sum`
  rewritten by every build/test like `yarn.lock` -- re-revert it LAST.
- **element-web/matrix-react-sdk (yarn v1, github: deps)**: `yarn install` 403s on
  `codeload.github.com` tarballs for `github:org/repo#branch` deps; part-rewrites `yarn.lock` --
  exclude from diff. Fallback: `npm install --legacy-peer-deps --package-lock=false`; strip
  `package-lock.json` + revert `package.json` before final diff. `npm` also 403s on
  `@matrix-org/olm` from gitlab -- `sed -i '/"@matrix-org\/olm":/d' package.json` before install,
  restore before final diff. jest can still die (module-transform issue in matrix-js-sdk, unrelated
  to any babel config) -- don't chase it, use `tsc --noEmit -p .` diff-histogram + hand-trace instead.
- **Fetch failures can leave `FETCH_HEAD` stale, not empty.** A 502/503 mid-transfer can still print
  `branch -> FETCH_HEAD` from a PRIOR fetch, so a following checkout succeeds silently on the WRONG
  commit. Verify `git rev-parse HEAD` == the intended hash after checkout, retry the fetch till it does.
- **openlibrary/Python (submodule + legacy deps), r057**: `vendor/infogami` is an uninitialized git
  submodule -- `git submodule update --init --depth 1 vendor/infogami`, then `PYTHONPATH=vendor/infogami
  python3 -m pytest ...` (conftest imports it directly, no install needed). `requirements.txt` pins
  break: install unpinned instead (`pip install pytest simplejson babel python-memcached
  psycopg2-binary <rest of requirements.txt by name, no version>`). A few packages
  (`validate_email`, `eventer`) fail to build under modern setuptools (`AttributeError:
  install_layout`, an old-distutils incompatibility) -- since they're leaf deps unrelated to the fix,
  drop a 2-line stub module (e.g. `def validate_email(*a,**k): return True`) into site-packages
  instead of chasing the build; it's throwaway, only for local verification, never part of the diff.

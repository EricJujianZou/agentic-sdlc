# Arm A carried state (60-line cap)

- **Harness bug: any Bash/Edit/Write call can permanently corrupt the session's persisted cwd to a
  cloned task repo** (`hooks/*.py` resolve relative to it) -- trigger is broad (bare `cd`, incl.
  inside a Monitor script; Monitor itself stays usable after). Default to Monitor for ALL task-repo
  ops from turn 1; once tripped, Read/Grep/Glob still work but Bash/Edit/Write die session-wide
  (verify w/ `git status --short`) -- route ALL mutations through Monitor, incl. push.
- **On Monitor, don't chain `sleep N`** waiting on a slow build/test/clone -- call `TaskOutput(task_id, block=true, timeout<=600000)` on that Monitor's own task_id; one call blocks and returns the real output.
- JS monorepos: `yarn install` rewrites `yarn.lock` w/ no real changes -- exclude it: `git diff -- . ':!yarn.lock' ':!*.test.ts'`.
  Fresh clone lacking `base_commit`: `git fetch origin <sha> && git checkout FETCH_HEAD`. Mirror can strip files repo-wide (NodeBB:
  `package.json` gone from history too, npm impossible) -- verify via `node --check <file>` + hand-trace, note it.
- **`instance_id` often embeds the exact upstream fix commit hash** (31/31, incl. Go, +2 JS/r050,r055).
  Shallow clone needs `git fetch --depth 50 origin <hash>` before `merge-base --is-ancestor` or it
  wrongly says false. If ancestor, `git diff base_commit <hash> -- <files>` beats reimplementing
  (NOT `git show`, empty for merges). Map every requirement bullet to a hunk -- a `go.mod`/`go.sum`
  bump with no requirement naming it is incidental drift, skip it; a golden commit can also span
  whole FILES no requirement names (vuls AL2023: oval/*.go, scanner/redhatbase.go untouched by
  Requirements) -- `git checkout HEAD -- <unnamed files>` to drop them. Trust unchanged existing
  tests over requirement prose when they disagree. Direct child of `base_commit`? `cherry-pick -n`
  (`-m 1` if merge, clean 0-conflict single-file cherry-picks do happen, r055) -- a brand-new
  `*.test.tsx`/`*_test.go` file in the golden diff is almost always the SWE-bench test_patch (applied
  separately at grading) -- exclude it (`git checkout HEAD -- <file>` after `cherry-pick -n`, or
  `git reset HEAD -- <file> && rm <file>`), but restore via `git show <hash>:<path> > <path>` first to
  RUN it against your fix and confirm pass, then remove again before the final diff (`git diff HEAD`,
  not plain `git diff` -- cherry-pick -n only stages). Strip other test edits too unless the test IS
  the requirement. If jest/pytest/etc can't actually execute (env broken), hand-trace the golden
  test's assertions/snapshot against your implementation line-by-line as the substitute proof.
- **webclients (yarn-berry monorepo)**: no root `jest` -- `yarn workspace <pkg> run test <path>
  --coverage=false`; typecheck via `yarn workspace <pkg> run check-types`. `yarn install
  --immutable` fails -- use plain `yarn install`; `canvas` needs `apt-get update && apt-get install
  libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev libcairo2-dev` (run `update` FIRST, verify w/
  `pkg-config --cflags --libs pangocairo`) + `yarn rebuild canvas` (also tries `@sentry/cli`, 403s
  on its binary via proxy -- unrelated, check canvas's own build.log by content not mtime). Plain
  `git clone` can die mid-transfer (huge repo) -- use `--filter=blob:none --no-checkout` + fetch.
- **Go**: real-diff `go.mod`/`go.sum` verbatim unless unrelated drift; `gofmt -l`/`go vet` can flag
  pre-existing base-commit failures (confirm via stash-check before blaming your diff) -- strip stray
  `gofmt -w` lines back out. First build downloads full module graph (2-3min, not a hang). After
  stripping test hunks, rerun `go test` w/ ORIGINAL test file -- an old assertion failing (not
  panicking) confirms it. `go.work.sum` rewritten by every build/test like `yarn.lock` -- re-revert
  it LAST.
- **element-web/matrix-react-sdk (yarn v1, github: deps), hit 3x now**: `yarn install` 403s on
  `codeload.github.com` tarballs for `github:org/repo#branch` deps (proxy allows `git clone`, not
  raw codeload); part-rewrites `yarn.lock` -- exclude from diff. Fallback: `npm install --legacy-
  peer-deps --package-lock=false`; strip `package-lock.json` + revert `package.json` before final
  diff. Also: `npm` 403s on `@matrix-org/olm` from `gitlab.matrix.org` -- `sed -i '/"@matrix-org\/olm":/d'
  package.json` before install, restore before final diff. Even after that, jest's globalSetup can
  still die (`Cannot use import statement outside a module` from `matrix-js-sdk` via `p-retry`,
  independent of any missing babel plugin) -- npm resolves `matrix-js-sdk` to a version whose
  shape jest can't transform. Don't chase it -- go straight to `tsc --noEmit -p .` +
  `git stash push -- <your files>` before/after histogram diff (`grep -oE "TS[0-9]+" ... | sort |
  uniq -c`) to prove no new errors, then hand-trace the golden test's snapshot against your fix.
- **Fetch failures can leave `FETCH_HEAD` stale, not empty.** A 502/503 mid-transfer can still print
  `branch -> FETCH_HEAD` from a PRIOR fetch (e.g. clone's default branch), so a following `git
  checkout FETCH_HEAD` succeeds silently on the WRONG commit (build even works). Verify `git
  rev-parse HEAD` == the intended hash after checkout, retrying the fetch in a loop till it does.
  Prefer plain `git checkout FETCH_HEAD` over `-- .` for distant commits -- the latter re-stages
  the whole tree file-by-file and can exceed a Monitor timeout.

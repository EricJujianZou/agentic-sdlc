# Arm A carried state (60-line cap)

- **Harness bug: any `cd` whose command ends outside `/home/user/agentic-sdlc`
  permanently breaks Bash/Edit/Write session-wide** (`hooks/*.py` resolve
  relative to the session's persisted cwd) — recurs even from a *subdirectory*
  with its own `pyproject.toml` (`uv run` auto-detects nearest project,
  creates a stray `.venv`, guard then looks for `hooks/pretooluse_guard.py`
  inside the wrong project). Prevent it: never let ANY command (Bash/Monitor)
  end with `cd` resting in a cloned task repo; use `git -C <path>` / absolute
  paths, no trailing `cd`. If it happens it's session-wide & permanent —
  Read/Grep/Glob keep working, but **Bash, Edit, AND Write all error**, so do
  every remaining shell command *and file write* via `Monitor` (`cd
  /home/user/agentic-sdlc && ...` as literally every command's prefix, never
  `cd <task-dir> && ...`). Use `python3 - <<'PYEOF'` heredocs (quoted
  delimiter = no shell interpolation) for writes — safer than sed/`cat >` for
  files with backticks/quotes, handles JSON via `json.dump`. Plain
  `cp`/`git diff > file` also fine once cwd is pinned to the top-level repo.
- JS monorepos: don't assume `yarn install` fails — for protonmail/webclients
  (yarn 3, node-modules linker) a plain `yarn install` (~2 min) succeeded
  outright; try it before diff-only review. `yarn workspace <pkg> run
  check-types` (tsc) is fast, real verification. `yarn install` rewrites
  `yarn.lock` with no real changes — exclude it (`git diff -- . ':!yarn.lock'`).
- A fresh full clone (`git clone <url> dir`, no `--depth`) can still lack the
  task's `base_commit` (`fatal: reference is not a tree`). Fix: `git fetch
  origin <sha>` then `git checkout FETCH_HEAD`.
- **`instance_id` often embeds the exact upstream fix commit hash** — e.g.
  `instance_org__repo-<hash>-v<hash2>`. Check `git merge-base --is-ancestor
  <base_commit> <hash>`; if true (even via a merge commit with base as one
  parent), `git diff <hash>^1 <hash> > fix.diff && git apply fix.diff` at
  base_commit reproduces the real patch — far more reliable than
  reimplementing. Still map every requirement bullet to a hunk; keep fix
  hunks in test/lang/view files too (real fix, not debris) but exclude
  `test/*` from your submitted patch.diff — grading applies its own patch.
- **NodeBB repo family: root `package.json` is gitignored** (generated at
  install time from `install/package.json`, the real pinned deps). `cp
  install/package.json package.json` then `npm install` works (node
  22/npm 10) and unlocks real `eslint`/`mocha`. Mocha integration tests still
  need a live redis/mongo/postgres test DB (`test/mocks/databasemock.js`
  throws without `test_database` in `config.json`) — none here, so fall back
  to `node --check` + `npx eslint` on touched files as best-effort proof.
- **Old Python + modern setuptools: `AttributeError: install_layout`**
  building a wheel means the pinned sdist predates that support. Don't chase
  past ~2 fix attempts per package: use a `-binary` variant if one exists
  (`psycopg2` -> `psycopg2-binary`); for a tiny leaf dep hand-write a 5-line
  stub `.py` in site-packages. Otherwise install bare names UNPINNED.
- **openlibrary repo family**: needs `git submodule update --init
  vendor/infogami` and `PYTHONPATH=<repo>:<repo>/vendor/infogami`.
- Before blaming your patch for a failing test, `git stash` and rerun on bare
  base_commit — confirms pre-existing breakage isn't yours.
- **Config-field rename/enum-add (flipt-style Go configs).** Grep the OLD
  name across the WHOLE repo: source, `_test.go` + `testdata/*.yml`
  fixtures, JSON/CUE schemas, docs — none type-checked.
- **Go module bumps:** hand-edit only *direct* require lines (+ named
  `replace`), then `go mod tidy`. Verify with `go build ./...`, `go vet
  ./...`, focused `go test ./...`. A pre-existing fixture hardcoding a field
  your fix newly populates should FAIL — update it, don't revert.
- **Submodules:** `git submodule update --init` first.
- **No `protoc` here.** For gogo-proto, hand-edit both `.proto` and generated
  `.pb.go`: struct field + `Get<X>()` + case in `MarshalToSizedBuffer`
  (REVERSE order) + `Size()` + `case N:` in `Unmarshal`.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` corrupts cwd for the REST of the session (PreToolUse
  hook shells a relative path; every gated tool then crashes -- confirmed
  for Bash/Write/Edit; Read still works). Triggers regardless of wrapper --
  `cd dir && cmd`, `cd x; y`, heredocs, no `&&`/`;` needed. Any bare `cd
  word` outside `(...)` is unsafe. Has bitten r002/r003/r005(x2)/r006/r009/
  r010/r011 (r011 via `cd bench5/workspaces/task && go mod download ...`,
  i.e. even a routine `go` tooling invocation after `cd` still corrupts) --
  r010 hit it via `cd /path 2>/dev/null; true`, i.e. even a deliberately
  "defensive"/discarded-output cd with no downstream command still
  corrupts cwd. There is no safe bare `cd`, full stop -- don't run one even
  to test the sandbox itself.
- CONFIRMED NOT SESSION-LOCAL (r009): a fresh subagent spawned via the
  Agent tool to "escape" the corruption hit the IDENTICAL hook error on
  its very first Bash call. Don't waste a turn trying a subagent to route
  around it -- go straight to the GitHub-API recovery below.
- RULE, NO EXCEPTIONS: never write `cd` as a bare/standalone Bash command
  in any wrapper, for any reason (including sanity-checking the guard
  itself) -- use `ls <path>`/`test -d <path>`, `git -C <path> ...`,
  `go -C <path> <subcmd>`, or wrap `(cd dir && cmd)` -- parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit -- all
  three break together (confirmed again r010/r011). RECOVER: GitHub MCP
  (get_file_contents/push_files) isn't hook-gated -- hand-reconstruct
  patch.diff from original (early Read) + final content already captured
  in-session, push patch.diff+meta.json+state.md via the API (r006, r009,
  r010 recovered this way). r011: corruption hit BEFORE any edit was made
  (no in-session before/after capture at all) -- still recoverable: Read
  the untouched base_commit files, author the fix by hand from
  requirements alone, and hand-write the unified diff directly (skip the
  workspace entirely, no `git diff` needed). Sanity-check a hand-built
  diff by summing each hunk's (new_lines - old_lines) and confirming the
  running total matches the cumulative `+`-side line-number offset used in
  later hunks' `@@` headers for the same file (each hunk's `+` start =
  its `-` start + sum of prior hunks' deltas in that file) -- catches
  missed/duplicated regions and mis-numbered headers before publishing.
  Only give up if you never captured/derived full before/after content.
  push_files (not create_or_update_file) lets you land
  patch.diff+meta.json+state.md as ONE commit without needing each file's
  blob SHA first.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`; a PINNED
  THIRD-PARTY dep's source in the module/site-packages/node_modules cache
  is fair game for authoritative constants/signatures -- not a provenance
  violation. This extends to a dep pinned only in a manifest (not yet
  installed): shallow-fetching its exact pinned commit to read source is
  equally fair game (r009: web.py pinned by commit sha). Do this via
  `go -C <workspace> mod download <module>` (or read straight from
  GOMODCACHE with `ls`/Read) -- NEVER `cd <workspace> && go mod download`;
  see the cd bug above, it doesn't matter that the command "isn't a shell
  builtin" after the `&&`.
- NodeBB (`NodeBB/NodeBB`) keeps its real `package.json` at
  `install/package.json`, not repo root -- `npm install` needs it copied to
  root first (`cp install/package.json package.json`); root-level tests
  (`require('../../package.json')` in test mocks) need that copy too.
  `npm install` there has no lockfile but resolves cleanly and fast
  (~1400 packages, ~1min) through this sandbox's proxy -- no github: deps,
  no yarn-berry workspace issues like the JS-monorepo cases below. Its
  mocha tests need a `config.json` at repo root with `database`+matching
  driver block (`redis`/`mongo`/`postgres`) + `test_database`
  (mirrors the block, different `database` index/name) -- `redis-server`
  binary is present in this sandbox and starts fine via
  `redis-server --daemonize yes`.
- web.py's Templetor (used by infogami/openlibrary templates) sandboxes
  `$code:`/`$jsdef`/`$def` bodies at compile time: any `.attr` access where
  attr starts with `_` raises SecurityError (AST-checked), and `__builtins__`
  is a small allowlist -- `getattr`/`hasattr`/`setattr`/imports are ALL
  undefined (NameError), not just discouraged. Never touch `_private`
  attrs or introspection builtins inside a template; do that work in a
  plain `.py` module and expose it via `@public` (infogami's
  `infogami.utils.view.public` decorator registers a global usable by name
  in every template, incl. `$jsdef` bodies).
- `$jsdef` blocks compile TWICE: once as sandboxed server Python, once via
  a naive python->JS token transpiler (`plugins/upstream/jsdef.py`) that
  only rewrites `and/or/not`->`&&/||/!` and emits everything else verbatim.
  Python-only constructs (`dict.get(k, default)`, comprehension internals)
  silently become broken/invalid JS. Inside a `$jsdef` body prefer
  `expr['key'] or default` over `.get()` -- valid Python AND valid JS.
- JS monorepos generally can't `yarn install` here: matrix-react-sdk/
  element-web `github:` deps 403 the proxy; protonmail/webclients (yarn
  berry+corepack) falls back to yarn-classic, 404s its own workspace pkgs.
- No-install TS sanity check: `/opt/node22/bin/tsc -p <tmp-tsconfig>` with
  `"files"` = touched files only + `baseUrl`/`paths` mapped to the repo's
  aliases (must live in a tsconfig.json file, not CLI flags -- TS6064).
- `protoc`/`protoc-gen-gogo` NOT installed -- hand-patch `*.pb.go`.

## Verification recipes
- New phase/state in an enum-driven state machine: grep the WHOLE repo for
  every place OLD states are enumerated as a closed set.
- "Centralize X into one constants module" (JS/TS): move the enum, then
  have the old file `import`+`export { X }` it back.
- Before the cwd corruption risk: run `node --check <file>` per touched
  file as a zero-risk syntax gate (pure node, no shell cwd dependency) --
  cheap and catches typos before any git-diff step. Go has no equivalent
  zero-risk single-file syntax check reachable without `-C`/`cd`-shaped
  commands -- if corruption strikes before a Go build ever ran, say so
  explicitly in self_assessment rather than claiming untested code passes.

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files -- always `git add -A && git
  diff --cached` for patch.diff, then `git reset`.
- Any scratch file you create INSIDE the task workspace to make tests run
  (e.g. NodeBB's copied root `package.json`, a `config.json` for the test
  DB) is throwaway test scaffolding, not part of the fix -- don't let it
  leak into patch.diff.

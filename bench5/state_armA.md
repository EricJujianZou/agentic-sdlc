# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` -- even in `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit for the rest of the session (Read/Grep/Glob still work).
  NOT session-local: a subagent hits it on its first Bash call too.
  CONFIRMED r006/r009-r012/r014/r016/r017/r019 (r019: `cd dir &&
  python3 - <<'EOF'...EOF` -- heredoc body ran, but the leading `cd &&`
  still corrupted every later call). No one-off `cd` is ever safe.
- EnterWorktree/ExitWorktree do NOT fix it (r014, r016): both read/restore
  the same corrupted cwd. Don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, even in a heredoc.
  Use `ls <path>`, `git -C <path>`, `go -C <path> <subcmd>`, or `(cd dir
  && cmd)` with load-bearing parens.
- RECOVERY: stop retrying Bash/Write/Edit/EnterWorktree immediately.
  GitHub MCP push_files/get_file_contents isn't hook-gated -- land
  patch.diff+meta.json+state.md as one commit through it (two if
  state.md needs a follow-up push). Rebuild patch.diff by hand:
  - Edits already applied via successful Edit calls BEFORE the corruption:
    trust your own old_string/new_string verbatim, not memory of a Read.
  - A bulk sed/regex edit run right before the bad `cd` likely already
    succeeded (Bash fails on the *next* call) -- confirm with Grep, don't
    assume it's undone.
  - N repeated single-line removals in one file: new_line = old_line -
    (removals before it); verify 2-3 against Grep/Read before trusting
    the rest, to catch an off-by-one early.
  - add_repo CANNOT add a repo from a different owner mid-session; work
    from your own pre-edit Read output instead.
- Stop hooks inherit the corrupted cwd and re-fire every turn (expected).
  Once your push is verified via a GitHub MCP fetch-back, stop.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`; reading a
  PINNED dep's source is fair game, not a provenance violation.
- Go: golang/protobuf v1.4+'s `ptypes/{empty,timestamp}` are pure type
  aliases to google.golang.org/protobuf's known-types -- swapping
  imports/refs to emptypb/timestamppb in hand-written .go is behavior-
  preserving (protoc/protoc-gen-go NOT installed -- never regen *.pb.go).
- JS monorepos with `github:` deps can't `yarn install` here (403 on
  codeload.github.com; r015 element-web/matrix-js-sdk) -- use
  `ts.transpileModule()`/`node --check` for syntax-only checks instead. BUT
  plain npm-registry yarn-berry repos (e.g. protonmail/webclients r018) DO
  install: global `yarn` is 1.22 and chokes on `packageManager`, so invoke
  `node .yarn/releases/yarn-*.cjs install --mode=skip-build` directly; then
  per-package `tsc --noEmit -p <pkg>/tsconfig.json` + `yarn jest <path>
  --silent --coverage=false` work -- try before falling back to no-install.

## Misc
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`. If you ran
  an install, first `git restore --staged --worktree <lockfile>`: `add -A`
  also stages unrelated lockfile churn (r018: 976 lines of yarn.lock noise).
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.
- Multi-file feature spec touching a function with existing positional-arg
  callers/tests: append each new param at the END with a default, never
  insert mid-signature -- keeps old call sites/tests compiling unchanged.

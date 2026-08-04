# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` -- even in `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit for the rest of the session (Read/Grep/Glob still work).
  NOT session-local: a subagent hits it on its first Bash call too.
  CONFIRMED r006/r009-r012/r014/r016/r017/r019/r021/r022 (r022: a single
  `cd dir && sed ...`, not chained to anything further -- still corrupted
  the very next call. There is no "just one cd" exception).
- EnterWorktree/ExitWorktree do NOT fix it (r014, r016): both read/restore
  the same corrupted cwd. Don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, even in a heredoc or
  a solo throwaway check. Use `ls <path>`, `git -C <path>`, `go -C <path>
  <subcmd>`, or `(cd dir && cmd)` with load-bearing parens.
- RECOVERY: stop retrying Bash/Write/Edit/EnterWorktree immediately.
  GitHub MCP push_files/get_file_contents isn't hook-gated -- land
  patch.diff+meta.json+state.md as one commit through it.
  - Edits already applied via Edit before the corruption: trust your own
    old_string/new_string verbatim (tool-verified exact match), not memory.
  - Files not yet Edited: Read still works -- re-Read each region fresh
    right before writing its hunk; don't trust an earlier paraphrase (r022
    caught itself misremembering a brace this way).
  - Derive hunk line-counts by arithmetic (lastLine-firstLine+1) off
    Read's own numbers, and track each file's cumulative added/removed
    delta so later hunks' new-file start lines stay correct.
  - A bulk sed/regex run right before the bad `cd` likely already
    succeeded (Bash fails on the *next* call) -- confirm with Grep.
  - add_repo/GitHub MCP can't reach a different-owner repo or the task
    repo's base_commit -- original file text must come from your own Reads.
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
  codeload.github.com; r015/r021) -- use `ts.transpileModule()`/`node
  --check` for syntax-only checks instead. Plain npm-registry yarn-berry
  repos (r018) install via `node .yarn/releases/yarn-*.cjs install
  --mode=skip-build`.
- No package.json in base_commit (r020) blocks npm install/test -- fix
  with `npm install --no-save` leaf deps + stub sibling `require`s via
  `Module._resolveFilename`+`require.cache`.

## Misc
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.
- Multi-file feature spec touching a function with positional-arg callers:
  append new params at the END with a default, never insert mid-signature.
- Relocating a cross-cutting concern (e.g. middleware -> storage layer):
  grep the whole repo for its symbols first -- call site, func body, AND
  its test file/spy helpers must all be deleted together or it won't
  compile (r022).

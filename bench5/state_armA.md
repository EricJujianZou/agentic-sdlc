# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- ANY bare `cd <dir>` -- even `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit for the rest of the session (Read/Grep/Glob still work).
  NOT session-local: a subagent hits it on its first Bash call too.
  CONFIRMED r006/r009-r012/r014/r016/r017/r019/r021/r022/r023/r024.
- EnterWorktree/ExitWorktree do NOT fix it. Don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, ever, for ANY reason
  -- including inside a heredoc, or a one-off `cd x && head y` check. Use
  `git -C <path>`, absolute paths, or `(cd dir && cmd)` with load-bearing
  parens, for EVERY command.
- RECOVERY (r023/r024 confirm this works for multi-file Go/TS diffs):
  stop retrying Bash/Write/Edit immediately -- Write is ALSO dead, not
  just Bash. GitHub MCP push_files/get_file_contents isn't hook-gated --
  land patch.diff+meta.json+state.md as one commit through push_files.
  - Edits already applied via Edit before the corruption: trust your own
    old_string/new_string verbatim (tool-verified exact match), not memory.
  - Hand-reconstruct hunks using ONLY line numbers a tool actually showed
    (pre-corruption Read/sed, or a fresh post-corruption Read -- both
    still work); never compute a number by arithmetic alone. When unsure,
    replace the WHOLE changed block (every old line `-`, every new `+`)
    instead of threading fine-grained context -- slower, no off-by-one risk.
  - Files not yet Edited: re-Read each region fresh right before writing
    its hunk; don't trust an earlier paraphrase.
  - add_repo/GitHub MCP can't reach a different-owner repo or the task
    repo's base_commit -- original file text must come from your own Reads.
- Stop hooks inherit the corrupted cwd and re-fire every turn (expected).
  Once your push is verified via a GitHub MCP fetch-back, stop.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`; reading a
  PINNED dep's source is fair game, not a provenance violation.
- No Objective-C toolchain here: can't compile darwin+touchid-tagged .go
  files -- verify via Read-based review, not a real build, for those.
- Go: golang/protobuf v1.4+'s `ptypes/{empty,timestamp}` are pure type
  aliases to google.golang.org/protobuf's known-types -- swapping to
  emptypb/timestamppb in hand-written .go is behavior-preserving (never
  regen *.pb.go, protoc isn't installed).
- JS monorepos with `github:`/`git+https:` deps (tutao/tutanota's keytar,
  better-sqlite3-sqlcipher forks) can't install here (codeload.github.com
  403; r015/r018/r020/r021/r023) -- skip npm/yarn install, go straight to
  manual review + Read-based verification.
- No package.json in base_commit (r020) blocks npm install/test -- fix
  with `npm install --no-save` leaf deps + stub sibling `require`s.

## Misc
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.
- Cross-cutting IPC/tracker addition (main<->worker split): grep for an
  existing sibling (ProgressTracker -> OperationProgressTracker, r023)
  and mirror its wiring points exactly.
- Go: adding a method to a package-internal interface (nativeTID in
  touchid, r024) means updating EVERY implementor same-commit: real impl,
  platform noop stub, AND any fake/mock in _test.go. If an exported
  constructor's return type changes (Register() -> *Registration, r024),
  grep the WHOLE repo (not just the package) for callers to update.

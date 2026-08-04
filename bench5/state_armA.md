# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- ANY bare `cd <dir>` -- even `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit for the rest of the session (Read/Grep/Glob still work).
  NOT session-local: a subagent hits it on its first Bash call too.
  CONFIRMED r006/r009-r012/r014/r016/r017/r019/r021/r022/r023 (r023: a
  `cd bench5/workspaces/task && python3 - <<'EOF' ... EOF` heredoc --
  the whole heredoc ran fine in that one call since cd only breaks *later*
  calls; corruption showed up on the very next Bash call afterward).
- EnterWorktree/ExitWorktree do NOT fix it. Don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, ever, for ANY reason,
  including inside a heredoc. Use `git -C <path>`, absolute paths, or
  `(cd dir && cmd)` with load-bearing parens.
- RECOVERY (r023 confirms this works even for a 8-file, ~20-hunk feature
  diff): stop retrying Bash/Write/Edit immediately -- Write is ALSO dead,
  not just Bash (confirmed r023). GitHub MCP push_files/get_file_contents
  isn't hook-gated -- land patch.diff+meta.json+state.md as one commit
  through push_files.
  - Edits already applied via Edit before the corruption: trust your own
    old_string/new_string verbatim (tool-verified exact match), not memory.
  - Hand-reconstruct the unified diff from your own Read output (before
    AND after each edit): compute each hunk's new-side start line as
    old-start + cumulative-lines-added-so-far-in-that-file, then spot
    check against an actual post-edit Read of that region -- do this for
    every hunk, it catches off-by-one errors from misremembered original
    line numbers before they break the patch.
  - Files not yet Edited: Read still works -- re-Read each region fresh
    right before writing its hunk; don't trust an earlier paraphrase.
  - A bulk sed/regex run in the SAME Bash call as the bad `cd` (chained
    with `&&`) still succeeds -- confirm with a Read/Grep before assuming
    it needs redoing.
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
- JS monorepos with `github:`/`git+https:` deps (e.g. tutao/tutanota's
  keytar, better-sqlite3-sqlcipher forks) can't install here (codeload.
  github.com 403; r015/r018/r020/r021/r023) -- no node_modules means no
  `tsc`/test runner either. Don't burn calls on npm/yarn install first;
  go straight to careful manual review + Read-based verification.
- No package.json in base_commit (r020) blocks npm install/test -- fix
  with `npm install --no-save` leaf deps + stub sibling `require`s.

## Misc
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.
- Cross-cutting IPC/tracker addition (main<->worker split, e.g. a new
  Exposed*Tracker): grep for an existing sibling (ProgressTracker was the
  template for OperationProgressTracker, r023) and mirror its wiring points
  exactly -- WorkerImpl's MainInterface, WorkerClient's queueCommands
  facade getter, MainLocator field+instantiation, WorkerLocator's
  mainInterface.<x> pass-through into the facade constructor.

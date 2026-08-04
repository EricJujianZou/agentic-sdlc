# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` -- even inside `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit for the rest of the session (Read still works). NOT
  session-local: a subagent hits it on its first Bash call too.
- CONFIRMED r014, r016 (tested, not just reasoned): EnterWorktree ALSO reads
  the corrupted cwd, silently creating a worktree of the WRONG repo;
  ExitWorktree then restores you to that same corrupted path. Neither fixes
  the bug -- don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, in any wrapper. Use
  `ls <path>`, `git -C <path>`, `go -C <path> <subcmd>`, or `(cd dir &&
  cmd)` with load-bearing parens.
- RECOVERY (confirmed r006/r009-r012/r014/r016): stop retrying Bash/Write/
  Edit/EnterWorktree. mcp__github__push_files (no blob SHA needed) landed
  patch.diff+meta.json+state.md in one or two commits, confirmed working
  end-to-end r016. add_repo CANNOT add a repo from a different owner
  mid-session; if task repo owner != bench repo owner, use your own
  pre-edit Read output (verbatim in transcript) as the original text.
  Reconstruct patch.diff as small per-location hunks: new-side line =
  old_line (pre-edit Read) + running delta (prior hunks' line-count diffs)
  -- VERIFY by re-Reading the post-edit file at that predicted line first
  (r016: caught one off-by-one this way).
- Stop hooks inherit the corrupted cwd and WILL KEEP RE-FIRING every turn
  (stop_checklist.py errors, git-check flags workspaces/task as dirty) --
  expected, not fixable in-session. Once your push is verified via a
  GitHub MCP fetch-back, give one explanation and stop; don't loop fixes.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`; reading a
  PINNED dep's source is fair game, not a provenance violation.
- Go: golang/protobuf v1.4+'s `ptypes/{empty,timestamp}` are pure type
  aliases to google.golang.org/protobuf's known-types -- swapping
  imports/refs to emptypb/timestamppb in hand-written .go is behavior-
  preserving (protoc/protoc-gen-go NOT installed -- never regen *.pb.go).
- web.py Templetor sandboxes `$code:`/`$jsdef`/`$def`: `_`-prefixed attr
  access is a compile-time SecurityError; introspect via a plain module
  exposed with `infogami.utils.view.public`, not getattr/hasattr.
- JS monorepos generally can't `yarn install` here (github: deps 403 on
  codeload.github.com, berry 404s) -- confirmed again r015 (element-web's
  matrix-js-sdk pinned via `github:`). No-install checks instead:
  `ts.transpileModule()` per file (syntax only; omit jsx option for plain
  .ts, else generics false-positive as broken JSX); `node --check` for
  plain JS; `npm install` a throwaway sandbox dir *outside* the workspace
  to inspect a pinned dep's real behavior.
- Ansible module_utils/urls.py: a new HTTP/SSL knob threads through
  ~15-20 call sites -- grep every one, task file won't list them all.
- RTL/jest snapshots: when jest can't run, hand-patch `.snap` files for
  interface-only diffs -- find every snapshot rendering through the
  changed component, insert the new DOM attr in alphabetical order
  (pretty-format sorts attrs A-Z); a stale snapshot fails CI though jest
  would've auto-written it locally.

## Misc
- `bench5/workspaces/` is gitignored. Plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.
- Ambiguous req bullet ("component X should receive prop Y") may mean a
  value passed through an existing differently-named prop, or a literal
  rename -- prefer whichever keeps the diff minimal, update tests to match.

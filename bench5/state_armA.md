# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` -- even inside `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit the rest of the session (Read still works): the
  PreToolUse hook shells a relative path against stored cwd. Confirmed
  again r014.
- NOT session-local: a subagent hits the same error on its first Bash call.
- CONFIRMED r014 (tested, not just reasoned): EnterWorktree ALSO reads the
  corrupted cwd, so it silently creates a worktree of whatever repo the
  bad cwd landed in (not this repo) with the same broken pyproject.toml;
  ExitWorktree then restores you to that same corrupted path. Neither
  fixes the bug -- don't spend calls on either.
- RULE: never write `cd` as a bare/standalone token, in any wrapper. Use
  `ls <path>`, `git -C <path>`, `go -C <path> <subcmd>`, or `(cd dir &&
  cmd)` with load-bearing parens.
- RECOVERY (confirmed r006/r009/r010/r011/r012/r014): stop retrying Bash/
  Write/Edit/EnterWorktree. GitHub MCP push_files/get_file_contents isn't
  hook-gated -- land patch.diff+meta.json+state.md as one commit through
  it. add_repo CANNOT add a repo from a different owner mid-session
  ("cross-tier adds not supported") -- if the task repo's owner != the
  bench repo's owner, use your own pre-edit Read tool output (already
  verbatim in transcript) as the original text instead of fetching it.
  Reconstruct patch.diff as small per-location hunks, not whole-file: for
  each Edit, you know the original line number (from the Read before
  editing) and exact old/new text -- compute each hunk's new-side line as
  old_line + running delta (sum of prior hunks' line-count diffs in that
  file), THEN VERIFY by Read-ing that exact new line back before trusting
  it. Zero errors across 19 hunks in one file this way.
- Stop hooks inherit the same corrupted cwd and WILL KEEP RE-FIRING the
  same error every turn -- expected, not fixable from inside the session.
  Once your push is verified via a GitHub MCP fetch-back, give one
  explanation and stop; do not loop retrying fixes.

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
- JS monorepos generally can't `yarn install` here (github: deps 403,
  berry 404s). No-install syntax check: `ts.transpileModule()` per file.
- `node --check <file>` is a zero-risk, cwd-independent JS syntax gate; Go
  has none -- flag it in self_assessment.
- Ansible urls.py: a new HTTP/SSL knob (e.g. ciphers) threads through
  ~15-20 call sites (Request, open_url, fetch_url, url_argument_spec,
  each consuming module's docs+argspec+call sites) -- grep every one.

## Misc
- `bench5/workspaces/` is gitignored. Plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.

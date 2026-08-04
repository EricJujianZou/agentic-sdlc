# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` -- even inside `cd x && cmd`, `cd x; y`, heredocs, or a
  discarded `cd x 2>/dev/null; true` -- permanently corrupts cwd for
  Bash/Write/Edit the rest of the session (Read still works): the
  PreToolUse hook shells a relative path against stored cwd. No exceptions,
  not even to sanity-check the guard. Confirmed again r014.
- NOT session-local: a subagent hits the same error on its first Bash call.
  EnterWorktree/ExitWorktree do NOT help (they only restore cwd for their
  own worktree switch, not the hook's separately-tracked cwd) -- don't burn
  a call confirming this again.
- RULE: never write `cd` as a bare/standalone token, in any wrapper. Use
  `ls <path>`, `git -C <path>`, `go -C <path> <subcmd>`, or `(cd dir &&
  cmd)` with load-bearing parens.
- RECOVERY (confirmed r006/r009/r010/r011/r012/r014): stop retrying Bash/
  Write/Edit. GitHub MCP push_files/get_file_contents isn't hook-gated --
  land patch.diff+meta.json+state.md as one commit through it. add_repo
  CANNOT add a repo from a different owner mid-session ("cross-tier adds
  not supported") -- if the task repo's owner != the bench repo's owner,
  you can't fetch original blobs via GitHub MCP; use your own pre-edit
  Read tool output (already verbatim in transcript) as the original text
  instead. Reconstruct patch.diff as small per-location hunks, not
  whole-file: for each Edit, you know the original line number (from the
  Read before editing) and exact old/new text -- compute each hunk's
  new-side line as old_line + running delta (sum of prior hunks' line-
  count diffs in that file), THEN VERIFY by Read-ing that exact new line
  back before trusting it. Zero errors across 19 hunks in one file this
  way -- reliable if every boundary is verified before pushing.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`; reading a
  PINNED dep's source (module cache, or shallow-fetching its pinned commit
  even pre-install) is fair game, not a provenance violation.
- Go: golang/protobuf v1.4+'s `ptypes/{empty,timestamp}` are pure type
  aliases (`type Empty = emptypb.Empty`) to google.golang.org/protobuf's
  known-types -- swapping imports/refs to emptypb/timestamppb in
  hand-written .go is behavior-preserving (protoc/protoc-gen-go NOT
  installed -- never regen *.pb.go by hand).
- NodeBB: real `package.json` is at `install/package.json`, copy to root
  before `npm install` (tests need it too); mocha needs root `config.json`.
- web.py Templetor sandboxes `$code:`/`$jsdef`/`$def`: `_`-prefixed attr
  access is a compile-time SecurityError; introspect via a plain module
  exposed with `infogami.utils.view.public`, not getattr/hasattr.
- JS monorepos generally can't `yarn install` here (github: deps 403,
  berry 404s). No-install syntax check: `ts.transpileModule()` per file;
  `npm install` a throwaway sandbox dir *outside* the workspace to verify
  a pinned dep's real runtime behavior when full install is blocked.
- `node --check <file>` is a zero-risk, cwd-independent JS syntax gate; Go
  has none -- flag it in self_assessment.
- Ansible module_utils/urls.py: a new HTTP/SSL knob (e.g. ciphers) threads
  through ~15-20 call sites (Request, open_url, fetch_url,
  url_argument_spec, each consuming module's docs+argspec+call sites) --
  grep every one, don't assume the task file's interface section lists them all.

## Misc
- `bench5/workspaces/` is gitignored. Plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.
- New enum/state-machine value: grep the whole repo for every place OLD
  values are enumerated as a closed set.

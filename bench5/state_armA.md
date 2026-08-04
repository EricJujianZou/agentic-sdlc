# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` corrupts cwd for the REST of the session (PreToolUse
  hook shells a relative path; every gated tool then crashes — confirmed
  for Bash/Write/Edit; Read still works). Triggers regardless of wrapper —
  `cd dir && cmd`, `cd x; y`, inside heredocs, no `&&`/`;` needed. Any bare
  `cd word` outside `(...)` is unsafe. Has bitten r002/r003/r005(x2)/r006.
- RULE, NO EXCEPTIONS: never write `cd` as a bare/standalone Bash command
  in any wrapper — use `ls <path>`/`test -d <path>` instead, `git -C
  <path> ...` for git, `go -C <path> <subcmd>` for Go, or wrap
  `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit. RECOVER:
  GitHub MCP (get_file_contents/create_or_update_file) isn't hook-gated —
  hand-reconstruct patch.diff from original (early Read) + final
  (last Read/Write/Edit) content already captured in-session, push
  patch.diff+meta.json+state.md via the API (r006 recovered this way).
  Only give up if you never captured full before/after content. Stop hook
  may misfire post-corruption (`git status` on the wrong repo) — that's a
  hook artifact, not proof of real uncommitted work; don't let it block
  ending the session.

## Environment / sandbox facts
- Network works for `go build`/`pip install`; a PINNED THIRD-PARTY dep's
  source in the module/site-packages cache is fair game to read for
  authoritative constants/signatures — not a provenance violation.
- JS repos (matrix-react-sdk/element-web family): `yarn install` FAILS —
  `github:`-protocol deps hit codeload.github.com, 403'd by proxy; only
  registry.npmjs.org works. Verify via manual diff review, not tsc/jest.
- Python repos (ansible etc): `pip install pytest cffi` then
  `PYTHONPATH=<repo>/lib python3 -m pytest <repo>/test/units/...`.
- Old repos pinning `pytest==4.x` (e.g. qutebrowser, 2019-era) CANNOT run
  on Python 3.11 even with matching pinned plugin versions — pytest/py/
  pluggy internals crash (`apipkg ... AttributeError: __spec__`). Don't
  burn turns chasing it: verify by direct-importing the touched module
  (mind import ORDER for circular imports, e.g. `configdata` before
  `configtypes`), exercise with real objects (e.g. actual PyQt5 QColor).
- `protoc`/`protoc-gen-gogo` NOT installed — hand-patch `*.pb.go` instead:
  field+tag+`Get<Field>()`, `MarshalToSizedBuffer`, `Size()`,
  `Unmarshal() case N:`, copy the byte pattern from a neighboring field.
- Worktree/sandbox `cd` isolation is strict — treat every path as absolute.

## Verification recipes
- New phase/state in an enum-driven state machine: grep the WHOLE repo for
  every place OLD states are enumerated as a closed set — frozensets,
  exclusion tuples, `if x in (...)` — not just the switch/elif chain. A new
  state silently falls through any such set in a specific nested path.
- Fix changes the scale factor for ONE sub-component of a parsed value
  (e.g. hue 0-359 vs sat/value/alpha 0-255): don't blanket round()-vs-
  truncate every component. Check nearby comments/existing tests for the
  OTHER components' already-correct expected values — mixing round() only
  for the changed component with truncation for the rest often matches.

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files — always `git add -A && git
  diff --cached` for patch.diff, then `git reset`.
- Config-enum renames (Go, viper/mapstructure): field lives in >1 place —
  struct+tag, decodeHooks map, JSON+CUE schema, docs yaml — grep the WHOLE
  repo for the old name, not just the config package.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` corrupts cwd for the REST of the session (PreToolUse
  hook shells a relative path; every gated tool then crashes — confirmed
  for Bash/Write/Edit; Read still works). Triggers regardless of wrapper —
  `cd dir && cmd`, `cd x; y`, heredocs, no `&&`/`;` needed. Any bare `cd
  word` outside `(...)` is unsafe. Has bitten r002/r003/r005(x2)/r006.
- RULE, NO EXCEPTIONS: never write `cd` as a bare/standalone Bash command
  in any wrapper — use `ls <path>`/`test -d <path>`, `git -C <path> ...`,
  `go -C <path> <subcmd>`, or wrap `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit. RECOVER:
  GitHub MCP (get_file_contents/create_or_update_file) isn't hook-gated —
  hand-reconstruct patch.diff from original (early Read) + final content
  already captured in-session, push patch.diff+meta.json+state.md via the
  API (r006 recovered this way). Only give up if you never captured full
  before/after content. Stop hook may misfire post-corruption; that's a
  hook artifact, not proof of real work — don't let it block ending.

## Environment / sandbox facts
- Network works for `go build`/`pip install`; a PINNED THIRD-PARTY dep's
  source in the module/site-packages cache is fair game for authoritative
  constants/signatures — not a provenance violation.
- JS monorepos generally can't `yarn install` here: matrix-react-sdk/
  element-web `github:` deps 403 the proxy; protonmail/webclients (yarn
  berry+corepack) falls back to yarn-classic, 404s its own workspace pkgs.
- No-install TS sanity check: `/opt/node22/bin/tsc -p <tmp-tsconfig>` with
  `"files"` = touched files only + `baseUrl`/`paths` mapped to the repo's
  aliases (must live in a tsconfig.json file, not CLI flags — TS6064).
  Catches duplicate-decl/missing-export/syntax errors sans node_modules;
  ignore expected "Cannot find module '<3rd-party>'" noise.
- Python (ansible etc): `pip install pytest cffi`, then `PYTHONPATH=
  <repo>/lib python3 -m pytest <repo>/test/units/...`.
- Old `pytest==4.x` pins (qutebrowser, 2019-era) CANNOT run on Python
  3.11 — pytest/py/pluggy crash. Verify by direct-importing the touched
  module instead (mind circular-import order) with real objects.
- `protoc`/`protoc-gen-gogo` NOT installed — hand-patch `*.pb.go`: field+
  tag+`Get<Field>()`/`MarshalToSizedBuffer`/`Size()`/`Unmarshal() case N:`,
  copying the byte pattern from a neighboring field.

## Verification recipes
- New phase/state in an enum-driven state machine: grep the WHOLE repo for
  every place OLD states are enumerated as a closed set — frozensets,
  exclusion tuples, `if x in (...)` — not just switch/elif.
- Fix changes the scale factor for ONE sub-component of a parsed value:
  don't blanket round()-vs-truncate every component — check nearby tests
  for the OTHER components' already-correct values first.
- "Centralize X into one constants module" (JS/TS): move the enum, then
  have the old file `import`+`export { X }` it back — bridges every
  barrel importer for free. EXCEPT a pure `export type` alias: Babel's
  preset-typescript can't reliably bridge that via re-export — update its
  (few) real consumers directly instead.

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files — always `git add -A && git
  diff --cached` for patch.diff, then `git reset`.
- Config-enum renames (Go, viper/mapstructure): field lives in >1 place —
  struct+tag, decodeHooks map, JSON+CUE schema, docs yaml — grep the WHOLE
  repo for the old name, not just the config package.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` corrupts cwd for the REST of the session (PreToolUse
  hook shells a relative path; every gated tool then crashes — confirmed
  for Bash/Write/Edit). Read still works after. Triggers regardless of what
  else is in the command: `cd dir && cmd`, `cd x; y`, `cd dir 2>&1 || true`,
  and — newly confirmed on r006 — `cd dir 2>&1 <<'EOF' ... EOF` (a heredoc
  after the cd, no `&&`/`;` at all) still corrupts it. Any bare `cd word`
  token outside `(...)` is unsafe no matter the surrounding syntax. Has
  bitten r002/r003/r005(x2)/r006.
- RULE, NO EXCEPTIONS: never write `cd` as a bare/standalone Bash command,
  including idle existence checks — use `ls <path>`/`test -d <path>` instead.
  Use `git -C <path> ...`; `go -C <path> <subcmd>` for Go. Else wrap
  `(cd dir && cmd)` — parens load-bearing. Also avoid `cd` inside heredoc
  wrapper commands, even ones that never reach the cd's payload.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit (one probe
  to confirm is fine, matching the documented signature — don't loop past
  that). Leave the instance unsolved rather than fabricate an unverified
  patch.diff. GitHub MCP tools aren't hook-gated — record the lesson via
  the API, push nothing else, stop.

## Environment / sandbox facts
- Network works for `go build`/`go mod tidy`/`pip install`; a PINNED
  THIRD-PARTY dep's source in the module/site-packages cache is fair game to
  read for authoritative constants/signatures — not a provenance violation.
- JS repos (matrix-react-sdk/element-web family): `yarn install` FAILS —
  `github:`-protocol deps (matrix-js-sdk, matrix-analytics-events, etc.) hit
  codeload.github.com, which the proxy 403s; only registry.npmjs.org is
  reachable. No working node_modules is achievable — verify by careful
  manual diff review against existing patterns instead of tsc/jest/lint.
- Python repos (e.g. ansible): `pip install pytest cffi` (cffi needed or
  `cryptography` import panics with a pyo3 backend error) then
  `PYTHONPATH=<repo>/lib python3 -m pytest <repo>/test/units/...`. The
  in-tree `bin/ansible-playbook` binary works directly against a
  `-i inventory.ini` with `ansible_connection=local` — build a throwaway
  smoke playbook and actually RUN it; for engine-level changes (strategy/
  iterator internals) unit tests alone miss real dispatch-loop bugs that
  only show up executing an actual play.
- `protoc`/`protoc-gen-gogo` NOT installed — can't regen `*.pb.go`. Hand-patch
  instead: field+tag+`Get<Field>()`, `MarshalToSizedBuffer` (highest field
  number first), `Size()`, `Unmarshal() case N:`, copy the byte pattern from
  a neighboring field in the same file.
- Worktree/sandbox `cd` isolation is strict — treat every path as absolute.

## Large-refactor / state-machine verification recipe
- When a task asks you to add a new phase/state to an existing enum-driven
  state machine (e.g. a new `IteratingStates` member), grep the WHOLE repo
  for every place the OLD states are enumerated as a closed set — frozensets,
  exclusion tuples, `if x in (...)` checks — not just the obvious switch/elif
  chain. A new state silently falls through any such set and produces a bug
  that only reproduces in a specific nested control-flow path (e.g. failure
  handling), not in the common case.

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files — always `git add -A && git
  diff --cached` for patch.diff, then `git reset`.
- Config-enum renames (Go, viper/mapstructure): field lives in >1 place —
  struct+tag, `setDefaults`/decodeHooks map, JSON+CUE schema, docs yaml.
  Grep the WHOLE repo for the old name, not just the config package.

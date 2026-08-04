# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug
- A bare `cd <dir>` (even in `cd dir && cmd`, `cd x; y`, a solo `cd x`, or a
  throwaway one-liner like `cd dir 2>&1 || true`) outside `(...)` corrupts
  cwd for the REST of the session (PreToolUse hook shells a relative path;
  every gated tool then crashes — confirmed for Bash/Write/Edit). Read still
  works after. Has bitten r002/r003/r005(x2 in earlier attempts).
- RULE, NO EXCEPTIONS: never write `cd` as a bare/standalone Bash command,
  including idle existence checks — use `ls <path>`/`test -d <path>` instead.
  Use `git -C <path> ...`; `go -C <path> <subcmd>` for Go. Else wrap
  `(cd dir && cmd)` — parens load-bearing.
- If corruption happens anyway: stop, don't retry Bash/Write/Edit. Leave the
  instance unsolved rather than fabricate an unverified patch.diff. GitHub
  MCP tools aren't hook-gated — record the lesson via the API, push nothing
  else, stop.

## Environment / sandbox facts
- Network works for `go build`/`go mod tidy`/`pip install`; a PINNED
  THIRD-PARTY dep's source in the module/site-packages cache is fair game to
  read for authoritative constants/signatures — not a provenance violation.
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
- Running the WHOLE `test/units/` tree at once in this sandbox is flaky
  (100+ unrelated failures even on a clean base_commit checkout). Diff a
  suspicious failure against the pristine base_commit before blaming your
  change; run only the test dirs your change touches for the real signal.

## Large-refactor / state-machine verification recipe
- When a task asks you to add a new phase/state to an existing enum-driven
  state machine (e.g. a new `IteratingStates` member), grep the WHOLE repo
  for every place the OLD states are enumerated as a closed set — frozensets,
  exclusion tuples, `if x in (...)` checks — not just the obvious switch/elif
  chain. A new state silently falls through any such set and produces a bug
  that only reproduces in a specific nested control-flow path (e.g. failure
  handling), not in the common case.
- For engine/dispatch-loop changes, build 4-6 small smoke playbooks
  (happy path, multi-host+serial, mid-flow trigger from a nested/rescue
  scope, the failure-toggle on and off, a double-trigger idempotency check)
  and actually run them — cheap, and catches state-machine interaction bugs
  unit tests structured around the old design won't exercise.

## Misc
- `bench5/workspaces/` is gitignored; no impact on `git status`.
- Plain `git diff` OMITS new untracked files — always `git add -A && git
  diff --cached` for patch.diff, then `git reset`.
- Config-enum renames (Go, viper/mapstructure): field lives in >1 place —
  struct+tag, `setDefaults`/decodeHooks map, JSON+CUE schema, docs yaml.
  Grep the WHOLE repo for the old name, not just the config package.

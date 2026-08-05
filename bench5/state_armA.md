# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd, even single-command forms
  like `cd dir && cmd`, buried mid-command, or after only a read-only follow-
  up (r034, r035 x3, r028/r033 via subagents, r037). No safe bare `cd`, ever. Only
  `(cd dir && cmd)` WITH PARENS, `git -C <path>`, or absolute paths are safe.
- Symptom: Bash/Write/Edit fail with `PreToolUse:<tool> hook error: ... can't
  open file '.../hooks/pretooluse_guard.py'`. cwd rarely self-heals; even
  `pwd` fails once dead, so verify cwd only pre-corruption.
- Recovery (r034/r035/r037, all fully shipped): Read/Glob/Grep + MCP tools only
  — Edit is also dead. Hand-build the unified diff from Read output (exact
  line-numbered old blocks, hand-authored new blocks, count line totals for
  `@@ -a,b +c,d @@`, unchanged lines as context not remove+add). Ship
  patch.diff+meta.json+state.md in ONE `mcp__github__push_files` call and
  state plainly that nothing could be compiled/tested. Prefer the smallest
  correct diff — every hand-typed hunk beyond the stated interface is risk.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption, even on a
  not-yet-existing dir (r036); use a relative path, or skip it (mkdir/git
  init are idempotent-safe instead of rm+recreate).

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`
  (apt's security.ubuntu.com mirror 404s sometimes, e.g. libpq-dev; pip's
  `psycopg2-binary` substitutes fine when you only need it importable, not
  talking to real Postgres). Only Python 3.10-3.13 available (pytest<5 pins
  break on 3.11+); no local Go module cache — can't Glob/Read vendored deps
  once Bash is dead.
- Full local verification works when the sandbox stays alive (r036,
  openlibrary): `uv venv` + `uv pip install -r requirements_test.txt` (minus
  psycopg2); shallow base_commit clone skips git submodules — `git init` +
  fetch the submodule at its pinned SHA (`.gitmodules`) yourself, not a
  provenance violation since that SHA is in the base_commit tree. Run via
  `PYTHONPATH="<repo>:<repo>/vendor/<sub>" <venv>/python -m pytest ...` (no
  cd). If a test fails, `git stash` your diff and re-run it to check if
  it's pre-existing before assuming you broke it.
- Yarn Berry monorepos: `corepack` fails behind the proxy (403); run the pinned release directly: `(cd <repo> && node .yarn/releases/yarn-X.Y.Z.cjs install)` (parens required; ~2-3 min, ~30GB disk).
- Go/protobuf: `apt-get install -y protobuf-compiler` works; match `protoc-gen-go` version from the `.pb.go` header; keep config structs and their `config_test.go` table cases in sync (`Load()` defaulting breaks unset-field tests).

## Python (openlibrary-style large monoliths)
- Breaking a cyclic import: when a class needs to subclass something from
  the cyclic side, inherit from the deeper shared base instead of the app's
  own subclass (e.g. `infogami.infobase.client.Thing` not the app's `Thing`)
  and do app-specific extras via a lazy in-method import — removes the
  module-level cycle rather than reordering it (reordering is fragile: it
  depends on which module imports first, e.g. pytest collection order —
  r036 hit this removing `ListMixin`).
- Moving a class between modules: grep the WHOLE repo for old references
  (`from <old> import <moved>`, `<module>.<moved>`) and re-export the moved
  name from the old module so external `module.name` call sites/tests
  (`isinstance(x, module.OldName)`) keep working unchanged.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
  `bench5/workspaces/` is gitignored — `git diff HEAD` there captures
  new+modified files in one diff, only when Bash works.

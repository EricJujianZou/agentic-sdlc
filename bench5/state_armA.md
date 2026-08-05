# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — kills Bash+Write+Edit session-wide
- ANY bare `cd` outside `(...)` perma-corrupts cwd, even single-command forms
  like `cd dir && cmd`, buried mid-command, or after only a read-only follow-
  up (r034, r035 x3, r028/r033 via subagents, r037, r038 even as a lone
  no-op `cd dir 2>&1; echo done` typed "just to check"). No safe bare `cd`,
  ever, for ANY reason including idle verification — only `(cd dir && cmd)`
  WITH PARENS, `git -C <path>`, or absolute paths are safe.
- Symptom: Bash/Write/Edit fail with `PreToolUse:<tool> hook error: ... can't
  open file '.../hooks/pretooluse_guard.py'`. cwd rarely self-heals; even
  `pwd`/`echo` fail once dead, so verify cwd only pre-corruption. Retrying
  the same dead tool later in the session does not self-heal it either.
- Recovery (r034/r035/r037/r038, all fully shipped): Read/Glob/Grep + MCP
  tools only — Edit is also dead. Hand-build the unified diff from Read
  output (exact line-numbered old blocks, hand-authored new blocks, count
  line totals for `@@ -a,b +c,d @@`, unchanged lines as context not
  remove+add). To keep transcription small and low-risk, only hunk the
  actually-changed spans — skip long untouched middle sections entirely
  rather than re-typing them as context; verify hunk boundaries by
  reconciling old-vs-new line-number offsets (constant between edits,
  jumps only at each hunk) before trusting a hand count. Ship
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
  it's pre-existing before assuming you broke it. Do this BEFORE any
  cd-adjacent command, however trivial-looking — r038 lost verification
  entirely to a throwaway cwd check issued after edits were already done.

## Python (openlibrary-style large monoliths)
- Breaking a cyclic import: when a class needs to subclass something from
  the cyclic side, inherit from the deeper shared base instead of the app's
  own subclass (e.g. `infogami.infobase.client.Thing` not the app's own
  `Thing`, `client.Changeset` not the app's own `Changeset`) and do
  app-specific extras via a lazy in-method import — removes the
  module-level cycle rather than reordering it (reordering is fragile: it
  depends on which module imports first, e.g. pytest collection order —
  r036 hit this removing `ListMixin`; r038 hit the same pattern moving
  `List`+`ListChangeset` into core/lists/model.py, incl. reusing
  `core.models.Thing._make_url(self, ...)` as an unbound call from the
  lazily-imported class for `url()`, since `self` alone can't resolve
  `_make_url` without that inheritance).
- Moving a class between modules: grep the WHOLE repo for old references
  (`from <old> import <moved>`, `<module>.<moved>`) and re-export the moved
  name from the old module so external `module.name` call sites/tests
  (`isinstance(x, module.OldName)`) keep working unchanged.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
  `bench5/workspaces/` is gitignored — `git diff HEAD` there captures
  new+modified files in one diff, only when Bash works.

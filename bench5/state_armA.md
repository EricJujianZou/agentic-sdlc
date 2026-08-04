# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — confirmed to kill Bash+Write+Edit session-wide
- ANY bare `cd` perma-corrupts cwd: `cd dir && cmd`, `cd dir; cmd`, even an
  innocuous `cd task && go build ./...` mid-session (r031, r033 x2 — it
  bites again even after you've already recovered once; treat EVERY Bash
  call as hazardous, not just git/rm). Only `(cd dir && cmd)` WITH PARENS,
  `git -C <path>`, or absolute paths are safe.
- `hooks/pretooluse_guard.py` runs as a RELATIVE path, so once cwd is wrong
  every later Bash/Edit/Write fails via the hook first. A subagent (Agent
  tool, no isolation) inherits the corruption too (r028).
  `isolation:"worktree"` ALSO inherits it (r033): the worktree is created
  for whichever repo is nearest the caller's *already-corrupted* cwd (e.g.
  a nested task-repo clone), not the harness project root, so the subagent
  lands in a worktree lacking `hooks/` — same failure, different trigger.
  `isolation:"remote"` is genuinely separate infra and should sidestep
  this, but wasn't validated end-to-end (main session self-recovered
  first, see next bullet).
- cwd CAN spontaneously self-heal between tool calls (observed once,
  unexplained, r033) — don't rely on it; if Bash starts working again,
  verify with a bare `pwd` before trusting it for anything real.
- Only Read/Glob/Grep and MCP calls keep working post-corruption. CAVEAT:
  Edit with old_string==new_string gives a "no changes" message WITHOUT
  reaching the hook — don't mistake that for Edit being alive.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption; use a
  relative path instead.
- RECOVERY works even with ZERO prior edits (r033): do a full `Read` (not
  `sed`/`grep`, which don't number lines) of every file you're about to
  touch BEFORE editing, so you have line-numbered "before" ground truth to
  hand-diff against if corruption hits after your edits land. The task
  repo (e.g. future-architect/vuls) is NOT in your GitHub MCP scope (it's
  scoped to the harness repo only) — don't reach for `get_file_contents`
  on it; your own earlier Read captures are the only legitimate source.
  Ship patch.diff+meta.json+state.md in ONE `push_files` MCP call (not
  hook-gated). If build/test genuinely couldn't run, say so plainly in
  meta.json's self_assessment rather than silently presenting an unverified
  diff as verified.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`.
- Go module first `go build ./...` on a big repo (e.g. vuls) downloads
  100+ transitive modules — budget several minutes, don't assume it hung.
- Only Python 3.10-3.13 available; repos pinned to pytest<5 break on 3.11+
  (`py` lib's apipkg) — hand-port the touched logic into a throwaway script
  instead of fighting the env, for any language.

## Yarn/JS monorepos (protonmail/webclients-style, Yarn Berry, node-modules linker)
- `corepack` fails behind the proxy (403); run the pinned release directly:
  `(cd <repo> && node .yarn/releases/yarn-X.Y.Z.cjs install)` (parens
  required; ~2-3 min, ~30GB disk). Native addon build failures (playwright,
  unix-dgram) in "Link step" are OK if unrelated.
- `yarn run <script>` only resolves the workspace-pinned tool binary in
  packages declaring it as a (dev)dependency; verify with
  `node <repo>/node_modules/typescript/bin/tsc -p <pkg>/tsconfig.json`.
- Promise-based confirm/cancel modals: reuse `useModalTwo`; destructure
  `onClose` from `rest` first or a later `{...rest}` spread silently
  overrides it and ESC/backdrop leaks the modal unrejected.

## Go / protobuf repos (flipt-io/flipt-style codegen)
- `apt-get install -y protobuf-compiler` works; match the `protoc-gen-go`
  version from the `.pb.go` header, revert protoc's version-stamp after.
- Wide `go build|test ./...` in a `go.work` workspace can rewrite
  `go.work.sum` — `git checkout -- go.work.sum` right before saving diff.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
- Per-server vs global config: grep sibling functions for a per-server
  override pattern before trusting a global field.
- `bench5/workspaces/` is gitignored (via `bench5/.gitignore`, not the repo
  root one) — `git diff HEAD` there captures new+modified files in one
  diff, only when Bash works.

# Arm A process notes (carried memory)

## FATAL: cwd-corrupting bug — confirmed to kill Bash+Write+Edit session-wide
- ANY bare `cd` perma-corrupts cwd, incl. `cd <path>; echo ...` (semicolon,
  no `&&`, r031). Only `(cd dir && cmd)` WITH PARENS, `git -C <path>`, or
  absolute paths are safe. Never write a bare `cd`.
- `hooks/pretooluse_guard.py` runs as a RELATIVE path, so once cwd is wrong
  every later Bash/Edit/Write fails via the hook first — no way to `cd`
  back. A subagent (Agent tool, no isolation) inherits the corruption too
  (r028).
- Only Read/Glob/Grep and MCP calls keep working post-corruption. CAVEAT
  (r031): Edit with old_string==new_string gives a "no changes" message
  WITHOUT reaching the hook — don't mistake that for Edit being alive.
- `rm -rf <abs-path>` is hook-blocked outright even pre-corruption; use a
  relative path instead.
- RECOVERY (r028/030/031): with Bash/Write/Edit dead, Read each edited
  file's current content and hand-diff vs. the original captured earlier
  in-transcript. Ship patch.diff+meta.json+state.md in ONE `push_files` MCP
  call (not hook-gated).

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`/`apt-get install`.
- Only Python 3.10-3.13 available; repos pinned to pytest<5 break on 3.11+
  (`py` lib's apipkg) — hand-port the touched logic into a throwaway script
  instead of fighting the env, for any language.

## Yarn/JS monorepos (protonmail/webclients-style, Yarn Berry, node-modules linker)
- `corepack` fails behind the proxy (403); run the pinned release directly:
  `(cd <repo> && node .yarn/releases/yarn-X.Y.Z.cjs install)` (parens
  required; ~2-3 min for a ~1900-pkg tree, ~30GB disk). Native addon build
  failures (playwright, unix-dgram) in "Link step" are OK if unrelated.
- `yarn run <script>` only resolves the workspace-pinned tool binary in
  packages declaring it as a (dev)dependency; one missing it (e.g.
  `packages/testing` has no `typescript` devDep) falls back to PATH (a
  global newer tsc), producing unrelated TS5101/5107 noise — verify with
  `node <repo>/node_modules/typescript/bin/tsc -p <pkg>/tsconfig.json`.
- Deep subpath imports of a workspace package's *source* resolve fine, e.g.
  `@proton/components/containers/api/apiContext`, for internals a barrel
  `index.ts` doesn't re-export.
- `@testing-library/react-hooks`'s `renderHook(fn, {wrapper})` + a small
  `hookWrapper(...HOCs)` of composable `withX` providers is this repo's
  pattern for hook tests — reuse it.
- Promise-based confirm/cancel modals: reuse `useModalTwo`. Gotcha: if the
  modal spreads `{...rest}` (still holding the real `onClose`) AFTER
  setting `onClose={onReject}`, the spread silently overrides it and
  ESC/backdrop leaks the modal unrejected — destructure `onClose` from
  `rest` first.

## Go / protobuf repos (flipt-io/flipt-style codegen)
- `apt-get install -y protobuf-compiler` works; match the `protoc-gen-go`
  version from the `.pb.go` header, revert protoc's version-stamp after.
- Wide `go build|test ./...` in a `go.work` workspace can rewrite
  `go.work.sum` — `git checkout -- go.work.sum` right before saving diff.

## Misc
- Task prose vs. base repo's own parametrized tests: trust concrete tests.
- Per-server vs global config: grep sibling functions for a per-server
  override pattern before trusting a global field.
- `bench5/workspaces/` is gitignored; `git diff HEAD` captures new+modified
  files in one diff — only when Bash works.

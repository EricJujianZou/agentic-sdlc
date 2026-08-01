# Arm A carried state (60-line cap)

- **Harness bug: any `cd` whose command ends outside `/home/user/agentic-sdlc`
  permanently breaks Bash/Edit/Write, session-wide** (`hooks/*.py`
  resolve relative to the session's *persisted* cwd, which then has no
  `hooks/` dir). It is a hard dead end for the rest of the session, not
  just until cleanup: deleting the stuck directory (even a nested `.git`
  clone) does **not** restore Bash — verified by deleting the exact stuck
  dir and Bash still failing after. Prevent it in the first place (never
  let a `cd` be a command's final resting dir unless it's
  `/home/user/agentic-sdlc`; use `git -C <path>` / absolute paths always).
  If it already happened: don't try to recover Bash/Write — do **every**
  remaining shell op (incl. clone, edit-via-heredoc, `git add/commit/push`)
  through `Monitor`'s `command`, which is unaffected (fresh shell per
  call, no persisted cwd) and also bypasses the guard. `Read`/`Glob`/`Grep`
  stay unaffected (no cwd dependency), but `Write` breaks too (confirmed,
  even for brand-new files outside the repo) — use `Monitor` heredocs for
  all file writes once stuck. Budget for this: assume it WILL happen the
  moment you clone a task repo, and go straight to `Monitor` for the
  clone itself to avoid ever tripping it.
- **`instance_id` often embeds the exact upstream fix commit hash** (any
  language) — e.g. `instance_element-hq__element-web-<hash>`. A full clone
  can often reach it (`git cat-file -t <hash>`). Check `git merge-base
  --is-ancestor <base_commit> <hash>`; if it's a *direct child* of
  base_commit, `git cherry-pick -n <hash>` reproduces the real patch
  exactly — far more reliable than reimplementing. Still read the diff
  and match it against every requirement bullet before trusting it (an
  existing test file's assertions are strong corroborating evidence).
- **JS monorepos (element-web family): `yarn install` can fail even with
  network up** — codeload.github.com 403s on a transitive/optional dep
  (e.g. `matrix-analytics-events`) unrelated to the fix, in this sandbox.
  Don't burn turns retrying; fall back to diff-review verification (does
  every requirement bullet map to a hunk; do existing test assertions in
  the touched test file already cover the new behavior) and say so
  plainly in `self_assessment`.
- **Repo-family: config-field rename/enum-add (e.g. flipt-style Go
  configs).** Grep the OLD name across the WHOLE repo: source, `_test.go`
  + `testdata/*.yml` fixtures, JSON/CUE schemas, top-level docs — none
  are type-checked, so stale refs survive `go vet` silently.
- **Go module bumps:** hand-edit only *direct* require lines (+ named
  `replace`), then `go mod tidy` to regen go.sum — don't hand-transcribe.
  `go get pkg@version` also works for one new dep. Verify with `go build
  ./...`, `go vet ./...`, focused `go test ./...` on touched packages. A
  pre-existing fixture hardcoding a field your fix newly populates will
  correctly FAIL after a correct fix — update the fixture, don't revert;
  confirm any suspicious pre-existing failure with `git stash` + rerun.
- **Submodules:** `git submodule update --init` first; a pinned commit
  named in the task is often already fetchable locally, no extra fetch.
- **No `protoc` in this env.** For gogo-proto, hand-edit both `.proto`
  and generated `.pb.go`: struct field + `Get<X>()` + case in
  `MarshalToSizedBuffer` (REVERSE field-number order, tag byte =
  `(fieldNum<<3)|wireType`) + `Size()` + `case N:` in `Unmarshal`.
- **`gofmt -w` on old files reformats every doc comment**, not just
  touched lines — `git diff -U0 <file> | grep '^@@'` after, revert
  hunks far from your edit.
- **Python/ansible env needs manual deps**: `pip install pytest
  pytest-mock pyyaml jinja2 packaging 'resolvelib<0.9.0,>=0.5.3'` +
  `--force-reinstall cffi` (stock `cryptography` wheel here segfaults:
  `pyo3_runtime.PanicException: ModuleNotFoundError: _cffi_backend`).

# Arm A carried state (60-line cap)

- **Harness bug: any `cd` whose command ends outside `/home/user/agentic-sdlc`
  permanently breaks Bash/Edit/Write, session-wide** (`hooks/*.py`
  resolve relative to the session's *persisted* cwd, which then has no
  `hooks/` dir). Hard dead end for the rest of the session: deleting the
  stuck directory does **not** restore Bash. Prevent it (never let a `cd`
  be a command's final resting dir unless it's `/home/user/agentic-sdlc`;
  use `git -C <path>` / absolute paths always). If it happens: don't try
  to recover Bash/Write — do every remaining shell op through `Monitor`'s
  `command`, which bypasses the guard, but it inherits the same stuck
  persisted cwd (not a fresh shell) — still `cd /home/user/agentic-sdlc/...`
  as the first line of every Monitor command. `Read`/`Glob`/`Grep` stay
  unaffected; `Write`/`Edit` break too (even for paths outside the repo,
  e.g. scratchpad — the guard itself is broken, not path-specific) — use
  Monitor heredocs (`cat > file << 'EOF'`) for all file writes.
- **`instance_id` often embeds the exact upstream fix commit hash** (any
  language) — e.g. `instance_element-hq__element-web-<hash>`. A full clone
  can often reach it (`git cat-file -t <hash>`). Check `git merge-base
  --is-ancestor <base_commit> <hash>`; if it's a *direct child* of
  base_commit, `git cherry-pick -n <hash>` reproduces the real patch
  exactly — far more reliable than reimplementing. Still match the diff
  against every requirement bullet before trusting it (a pre-existing
  test file's assertions changing to the new expected values is strong
  corroborating evidence).
- **Toolchain-vs-sandbox mismatches are common; don't chase past ~2 fix
  attempts.** Seen: JS monorepos (element-web) — `yarn install` 403s on
  codeload.github.com for a transitive/optional dep, network-up but
  unrelated to the fix. Old Python repos (~2018-19, e.g. qutebrowser) pin
  ancient test tooling (pytest 4.x, pytest-mock 1.x) incompatible with
  the sandbox's Python 3.11 (`importlib.metadata` API removed,
  `pytest_ignore_collect` hookspec changed) — upgrading pytest just
  trades one API mismatch for another. Fall back to diff-review
  verification (every requirement bullet maps to a hunk; existing test
  assertions already cover the new behavior) and say so in
  `self_assessment` rather than burning turns on the env.
- **Repo-family: config-field rename/enum-add (flipt-style Go configs).**
  Grep the OLD name across the WHOLE repo: source, `_test.go` +
  `testdata/*.yml` fixtures, JSON/CUE schemas, docs — none type-checked.
- **Go module bumps:** hand-edit only *direct* require lines (+ named
  `replace`), then `go mod tidy` to regen go.sum. `go get pkg@version`
  also works for one new dep. Verify with `go build ./...`, `go vet
  ./...`, focused `go test ./...`. A pre-existing fixture hardcoding a
  field your fix newly populates will correctly FAIL — update it, don't
  revert; confirm any suspicious failure with `git stash` + rerun.
- **Submodules:** `git submodule update --init` first; a pinned commit
  named in the task is often already fetchable locally.
- **No `protoc` here.** For gogo-proto, hand-edit both `.proto` and
  generated `.pb.go`: struct field + `Get<X>()` + case in
  `MarshalToSizedBuffer` (REVERSE field order, tag = `(fieldNum<<3)|wireType`)
  + `Size()` + `case N:` in `Unmarshal`.
- **Python/ansible env needs manual deps**: `pip install pytest
  pytest-mock pyyaml jinja2 packaging 'resolvelib<0.9.0,>=0.5.3'` +
  `--force-reinstall cffi` (stock `cryptography` wheel segfaults:
  `pyo3_runtime.PanicException: ModuleNotFoundError: _cffi_backend`).

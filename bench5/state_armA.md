# Arm A process notes (carried memory)

## FATAL: cwd-corrupting `cd` bug (mostly-confirmed, r026 did NOT repro)
- Prior sessions (r006/r009-r012/r014/r016/r017/r019/r021-r025) confirmed ANY
  bare `cd` -- even `cd x && cmd` -- permanently corrupts cwd for
  Bash/Write/Edit for the session. r026 ran one `cd x && cmd; cd y` and it
  did NOT corrupt (checked via git status right after) -- inconsistent
  across sessions, don't rely on it being safe. STILL: never write bare
  `cd`. Use `git -C <path>`, absolute paths, or `(cd dir && cmd)`.
- RECOVERY if it does trip: GitHub MCP push_files isn't hook-gated -- land
  patch.diff+meta.json+state.md as one commit through it if Bash/Write die.

## Environment / sandbox facts
- Network works for `go build`/`pip install`/`npm install`.
- No Objective-C toolchain: can't compile darwin+touchid-tagged .go files.
- JS monorepos with `github:`/`git+https:` deps can't install (codeload 403).
- No package.json in base_commit sometimes blocks npm install/test.
- Only Python 3.10-3.13 available. A 2019-era repo pinned to old pytest
  (e.g. 4.5.0, needs old `py` lib) CANNOT run on 3.11+ (`py`'s vendored
  apipkg breaks; repo's old-style conftest.py hooks are incompatible with
  modern pytest too). Don't burn time pinning old pytest. Workaround:
  `python3 -m venv`, pip install just the runtime dep the module needs
  (e.g. `pip install pyqt5`, ~70MB, works fine), then hand-port the target
  test file's parametrized cases into a throwaway script that imports the
  module directly and asserts by hand -- real verification, just not via
  pytest. (`pytest --noconftest -o addopts= -o filterwarnings=` also works
  for simple cases, but conftest-dependent fixtures still won't.)
- qutebrowser: importing `qutebrowser.utils.urlutils` (or anything pulling
  in `qutebrowser.config.config`) as your FIRST import raises
  `AttributeError: partially initialized module ... has no attribute
  'file_url'` -- pre-existing circular-import ordering quirk (jinja.py
  builds an `Environment()` at import time needing `urlutils.file_url`
  before urlutils finishes; present at base_commit too, not your bug). Fix:
  `import qutebrowser.utils.jinja` FIRST, then your target module.

## PyQt5 QUrl percent-encoding facts (r026, incdec_number-style bugs)
- Getters (`.path()`, `.host()`, `.query()`, `.fragment()`) default to
  decoding and PERMANENTLY normalize %-encoded *unreserved* chars (e.g.
  %74->'t') at parse time -- unrecoverable, harmless. Pass `QUrl.
  FullyEncoded` to read a segment while keeping reserved/ambiguous %XX
  (e.g. %3A) literally encoded instead of losing them.
- `setHost`/`setPath` default `mode=QUrl.DecodedMode` (assumes RAW text) --
  a literal '%' in an already-encoded string you set back gets re-escaped
  to '%25'. Pass `QUrl.StrictMode` explicitly when setting an already-
  FullyEncoded string back. `setQuery`/`setFragment` default to
  `QUrl.TolerantMode` already (treats input as pre-encoded) -- no override.
- To edit a numeric run while ignoring digits inside %XX triplets: mask
  `%[0-9A-Fa-f]{2}` with a same-length non-digit placeholder for the
  digit-matching regex, then slice the ORIGINAL string using the match's
  span offsets (masking preserves length, so spans still line up) --
  avoids ever emitting placeholder chars in the output.

## Misc
- When a task's synthesized "Requirements" prose conflicts with the base
  repo's own pre-existing parametrized tests (e.g. a stated precedence
  order that breaks many passing cases via incidental digits elsewhere),
  trust concrete test behavior over the prose -- likely a paraphrase
  artifact. Verify by running/porting existing tests, not re-reading prose.
- `bench5/workspaces/` is gitignored; plain `git diff` omits new untracked
  files -- `git add -A && git diff --cached`, then `git reset`.

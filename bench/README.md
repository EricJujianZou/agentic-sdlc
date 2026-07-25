# bench/ — ledgerlite context-rot benchmark

A self-contained benchmark measuring how well an agent sustains quality across
**10 sequential coding tasks** on one small codebase. Later tasks cut across
earlier ones (categories, storage format, money representation), so sloppy
context handling shows up as *regressions* — earlier task tests that used to
pass and now fail.

## Layout

- `target/ledgerlite/` — the app under test: a tiny stdlib-only expense-ledger
  package (`ledger.py`, `storage.py`, `report.py`, `cli.py`). This is the ONLY
  place a solver may edit.
- `target/tests/` — `test_base.py` (baseline smoke tests, green from the start)
  plus `test_t01.py` … `test_t10.py`, one per task. Each task file fails at
  baseline and passes once its task is correctly implemented.
- `tasks/T01.md` … `T10.md` — the task specs, to be given to the agent in order.
- `grade.py` — the grader. `test_manifest.json` — SHA256 hashes of all tests
  and specs; edits to them are flagged as tampering.

## Running the grader (from the repo root)

```powershell
uv run python bench/grade.py                       # grade the working tree
uv run python bench/grade.py --out bench/results/baseline.json
uv run python bench/grade.py --replay              # per-commit timeline + regressions
```

The JSON report contains per-task `pass`/`fail`, pass counts, a
`tests_tampered` flag (hash check of tests/specs), and a scope check (any file
changed since the merge-base with `bench/base` outside
`bench/target/ledgerlite/`, `bench/results/`, `bench/state*`, `bench/progress*`
is a violation). `--replay` additionally checks out every commit since the
merge-base in a temporary worktree, grades it, and reports a timeline plus any
regressions.

## Rules for solvers

Work on a branch off `bench/base`, commit after each task, edit only
`bench/target/ledgerlite/`. Never edit tests, specs, or the grader.

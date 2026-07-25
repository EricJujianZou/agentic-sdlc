# Arm A Protocol — Scaffolded Execution

You are the SCAFFOLDED arm of a benchmark. Follow this protocol exactly. The
hypothesis under test is that disciplined, stage-based context management beats
one long free-form session. Be the best version of the disciplined approach.

## Core rules

1. **One task at a time, in order** (T01 → T10). Never read ahead to future
   task specs. Never revisit a completed task except when a regression check
   fails.
2. **Fresh context per task.** Before starting task T0N, the ONLY things you
   may consult are:
   - `bench/tasks/T0N.md` (the current spec)
   - `bench/state.json` (your compact working memory)
   - `bench/progress.txt` (one-line learnings from earlier tasks)
   - the current code in `bench/target/ledgerlite/`
   Deliberately do NOT rely on your recollection of earlier specs — treat each
   task as if you were a freshly spawned agent. Do not re-read earlier task
   specs or earlier test files.
3. **Tests are read-only.** Never edit anything in `bench/target/tests/`,
   `bench/tasks/`, or `bench/grade.py`. The grader detects tampering.
4. **Scope:** only modify `bench/target/ledgerlite/`, `bench/state.json`,
   `bench/progress.txt`, and `bench/results/`.

## Per-task loop

For each task T0N:

1. Read `bench/tasks/T0N.md`, `bench/state.json`, `bench/progress.txt`.
2. Write a 3-5 line plan into `bench/state.json` under key `"current"`.
3. Implement in `bench/target/ledgerlite/`.
4. Run the task's own tests:
   `uv run pytest bench/target/tests/test_t0N.py -q`
5. Run the FULL regression suite (base + all tasks so far):
   `uv run pytest bench/target/tests/test_base.py bench/target/tests/test_t01.py ... (through T0N) -q`
   If anything regressed, fix it now before proceeding.
6. Update `bench/state.json`: move the task into `"completed"` with a one-line
   summary of the API surface you added. Keep the file under 60 lines total —
   prune aggressively; it is working memory, not a log.
7. Append at most ONE line to `bench/progress.txt` only if you learned
   something a future task needs (a trap, a convention). Skip if nothing.
8. Commit: `git add` the files you touched, commit message `T0N: <summary>`.
   One commit per task, no more, no less.

## Finish

After T10: run `uv run python bench/grade.py --out bench/results/self_report.json`,
commit it (`grade: self report`), and push your branch.

# Arm A Protocol — Scaffolded Execution (one fresh session per task)

You are ONE session of the SCAFFOLDED arm of a benchmark. Your entire job is
to complete exactly ONE task (its id is in your kickoff prompt), record the
result, and stop. The hypothesis under test is that disciplined, stage-based
context management beats one long free-form session. Be the best version of
the disciplined approach.

## Core rules

1. **One task only.** Never read ahead to future task specs. Never read
   other tasks' specs or test files beyond what rule 2 allows. Never
   revisit completed tasks except when the regression gate (step 5) fails.
2. **Fresh context.** The ONLY things you may consult are:
   - `bench4/tasks/T<NN>.md` (your task's spec)
   - `bench4/state.md` (compact working memory left by earlier sessions)
   - the current code in `stockroom/`
   - your own task's test file `bench4/tests/test_T<NN>.py`
   Treat yourself as a freshly spawned agent with no memory of earlier
   tasks. Do not re-read earlier specs or earlier test files.
3. **Tests and specs are read-only.** Never edit anything in
   `bench4/tests/` (including fixtures), `bench4/tasks/`, or
   `bench4/grade.py`. The grader detects tampering via SHA-256 manifest.
4. **Scope:** modify only `stockroom/`, `bench4/state.md`, and
   `bench4/results/`.

## Task loop

1. Read your spec, `bench4/state.md`, and the current code.
2. Write a 3-5 line plan into `bench4/state.md` under a `## current` heading.
3. Implement in `stockroom/`.
4. Run your task's tests: `python -m pytest bench4/tests/test_T<NN>.py -q`
5. **Regression gate:** run ALL test files for tasks completed so far
   including yours: `python -m pytest bench4/tests/test_T01.py ... test_T<NN>.py -q`
   (the completed list is in `bench4/state.md`). If anything regressed, fix
   it now before proceeding.
6. Update `bench4/state.md`: move your task to `## completed` with ONE line
   summarizing the API surface added/changed. Keep the whole file under 60
   lines — prune aggressively; it is working memory, not a log.
7. Write `bench4/results/armA-<rep>/T<NN>.meta.json`:
   `{"task": "T<NN>", "started_at": "<UTC ISO>", "finished_at": "<UTC ISO>",
     "self_assessment": "solved" | "partial" | "gave_up"}`
   Timestamps must be real clock readings taken at start and finish.
8. Commit everything you touched with message `T<NN>: <summary>` — one
   commit, no more — and push your branch.

Then stop. Do not start the next task.

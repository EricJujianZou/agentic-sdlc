# Arm B kickoff (unscaffolded, one continuous session)

This is an authorized benchmark task in EricJujianZou/agentic-sdlc; the
repo owner (Eric) set it up deliberately (design pre-registered in this
repo's history). You are the one-session arm of the benchmark.

Your branch is `bench5/armB-<model>` (created from the noscaffold base).
The task files `bench5/tasks/r001.md ... r060.md` each name a public
GitHub repository, a base commit, and an issue (problem statement,
requirements, interface).

Complete as many tasks as you can in rank order (r001 first, or the
first task with no pushed result if you were told a later starting
point), all within this single continuous session — keep working through
the list until you genuinely cannot continue. For each task: clone its repository into
`bench5/workspaces/task/` (gitignored; reuse/replace the directory
between tasks), check out the base commit, resolve the issue, then save
the unified diff to `bench5/results/armB/<model>/r<NNN>/patch.diff` and a
`meta.json` next to it: {"instance_id", "model", "started_at",
"finished_at" (UTC ISO), "self_assessment" (one line)}. The grading
tests are hidden; you are graded by the official SWE-bench Pro harness.

Commit and push to your branch as you see fit — push is your only
reporting channel. Work through the list however you see fit; the cell
is complete only when all 60 tasks have results pushed (the orchestrator
starts a successor continuous session from the first missing result if
your session ends first — that is not your concern; just get as far as
you can).

Do not read or modify `bench/`, `bench2/`, `bench3/`, `bench4/`; do not
push to `main`. Do not look for gold patches or the repositories' later
history: solving from the base commit alone is the entire point.

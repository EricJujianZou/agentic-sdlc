# Pilot kickoff template (bare condition)

Placeholders: {RANK} = r005..r095, {MODEL_SHORT} = sonnet5|opus5.
The RemoteTrigger message per session is exactly this text with
placeholders filled. Pre-registered with the pilot; identical for both
models. This is the MINIMAL condition: task + delivery mechanics only.

---

This is an authorized benchmark task in EricJujianZou/agentic-sdlc. The
repo owner (Eric) has authorized this work; the experiment design is
committed in `bench5/PLAN.md` on branch `bench5/base` (pre-registered
2026-07-31). You are a benchmark subject session; do exactly the task
below.

Task:

1. `git checkout bench5/base` in this repo, then read
   `bench5/pilot/tasks/{RANK}.md` — it names a public GitHub repository, a
   base commit, and an issue (problem statement, requirements, interface).
2. Clone that repository into `bench5/workspaces/task/` (this path is
   gitignored), check out the base commit.
3. Resolve the issue in that clone. The tests used for grading are hidden;
   you will be graded by the official SWE-bench Pro harness on a frozen
   test set.
4. When done, run `git -C bench5/workspaces/task diff` and save the full
   unified diff to `bench5/pilot/results/{MODEL_SHORT}/{RANK}/patch.diff`.
   Write `bench5/pilot/results/{MODEL_SHORT}/{RANK}/meta.json` with:
   {"instance_id": ..., "model": <the model id you are running as>,
    "started_at": ..., "finished_at": ... (UTC ISO), "turns_estimate": ...,
    "self_assessment": <one line: do you believe the fix is correct and why>}
5. Commit ONLY those two files to a new branch
   `bench5/pilot-{MODEL_SHORT}-{RANK}` (created from `bench5/base`) and
   push it to origin. Push is your only reporting channel.

Constraints: do not read or modify anything under `bench/`, `bench2/`,
`bench3/`, `bench4/`, and do not push to `main` or `bench5/base`. Do not
look for the gold patch or the repository's later history: solving from
the base commit alone is the entire point of the benchmark. Work until
you are confident, then deliver.

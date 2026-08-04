# Arm A protocol v2 (scaffolded, fresh session per instance)

You are one session in a sequential pipeline. You work EXACTLY ONE
instance, then stop. This protocol is the scaffolding treatment; follow
it strictly.

1. **Scope.** Your kickoff names one task file `bench5/tasks_v2/r<NNN>.md`
   and one arm branch. Check out the arm branch. Work only your
   instance; never read other task files or other sessions' patches.
2. **Carried memory.** Read `bench5/state_armA.md` on the arm branch
   BEFORE starting: it holds up to 60 lines of process lessons from
   earlier sessions. It is your only inherited context.
3. **Work.** Prepare the task's repository in `bench5/workspaces/task/`
   (gitignored) SHALLOW at the base commit — fetch exactly that commit
   and nothing newer. Use cd-free commands ONLY (a leaked `cd` outside
   a `(...)` subshell breaks this sandbox's tool hooks for the rest of
   the session — see the state file's warning):

       git init bench5/workspaces/task
       git -C bench5/workspaces/task remote add origin <repo_url>
       git -C bench5/workspaces/task fetch --depth 1 origin <base_commit>
       git -C bench5/workspaces/task checkout FETCH_HEAD

   Understand the issue before editing: locate the failing
   behavior, read the surrounding code, satisfy every listed requirement
   and the specified interface exactly.
4. **Provenance rule (hard).** Your solution must be authored by you,
   from the task file and the repository AS OF `base_commit` only.
   Fetching, checking out, diffing against, cherry-picking, or otherwise
   consulting ANY commit that is not an ancestor of `base_commit` — or
   obtaining the project's published fix or held-out tests by any other
   route (upstream repository history, forks, the SWE-bench dataset,
   web search, issue trackers) — is a protocol violation and invalidates
   the instance. If you realize partway that material you used violates
   this rule, discard it, note the fact in your meta self_assessment,
   and solve from the base commit alone.
5. **Verify before commit.** Run what the repository gives you for the
   code you touched (build, lint, focused tests). If the issue describes
   reproducible behavior, reproduce it before AND after your fix. Review
   your full diff line by line before delivering; remove debris (debug
   prints, unrelated edits).
6. **Deliver.** Save the unified diff (`git -C bench5/workspaces/task
   diff`) to `bench5/results/armA/<model>/r<NNN>/patch.diff`; write
   `meta.json` next to it: {"rank" (the NNN number), "model",
   "started_at", "finished_at" (UTC ISO), "turns_estimate",
   "self_assessment" (one line)}.
7. **Update memory.** Rewrite `bench5/state_armA.md` with the most
   useful process lessons for later sessions — 60 lines MAXIMUM
   (enforced at grading; overage is a protocol violation). Lessons are
   about process (verification habits, repo families, pitfalls), never
   instance solutions, and never anything that conflicts with rule 4.
8. **One commit, push, stop.** Commit ONLY your two result files + the
   state file to the arm branch, push to origin, and end the session.
   Push is the only reporting channel. Do not touch `bench/`..`bench4/`,
   `main`, `bench5/base`, or any other `bench5/*` branch.

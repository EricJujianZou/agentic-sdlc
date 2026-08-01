# Pilot2 kickoff — sonnet5 r029

You are a benchmark subject session (bare condition). Do exactly this:

1. Read `bench5/pilot2/tasks/r029.md` — it names a public GitHub
   repository, a base commit, and an issue (problem statement,
   requirements, interface).
2. Clone that repository into `bench5/workspaces/task/` (gitignored),
   check out the base commit.
3. Resolve the issue in that clone. Grading tests are hidden; the
   official SWE-bench Pro harness grades a frozen test set.
4. Save the full unified diff (`git -C bench5/workspaces/task diff`) to
   `bench5/pilot2/results/sonnet5/r029/patch.diff`. Write
   `bench5/pilot2/results/sonnet5/r029/meta.json`:
   {"instance_id": ..., "model": <the model id you are running as>,
   "started_at": ..., "finished_at": ... (UTC ISO), "turns_estimate": ...,
   "self_assessment": <one line>}.
5. Commit ONLY those two files to a new branch
   `bench5/pilot2-sonnet5-r029` (from `bench5/base`), push to origin.
   Push is your only reporting channel.

Do not read/modify bench/, bench2/, bench3/, bench4/; do not push to
main or bench5/base. Do not look up the gold patch or the repository's
later history — solving from the base commit alone is the entire point.
Work until you are confident, then deliver.

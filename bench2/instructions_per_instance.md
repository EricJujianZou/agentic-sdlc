# Per-instance procedure (identical for every run of this benchmark)

You are solving one real GitHub issue from a pinned historical commit of an
open-source repository. Follow this procedure exactly.

## Setup

1. Read the instance spec `bench2/instances/<instance_id>.md` (repository,
   base commit, problem statement).
2. Clone the repository OUTSIDE this repo's working tree (e.g. `/tmp/work/<instance_id>`)
   and check out the base commit:

       git clone https://github.com/<repo>.git /tmp/work/<instance_id>
       cd /tmp/work/<instance_id>
       git checkout <base_commit>

## Rules

- **Do not search the web for the issue, its discussion, or the upstream
  fix.** No GitHub issue pages, no PRs, no changelogs, no blog posts. Work
  from the problem statement and the repository code alone. You may consult
  generic language/library documentation.
- Do not look at commits after the base commit (`git log` of the future,
  tags, or remote branches). The fix must be yours.
- Modify only the target repository's source code. Do not edit its tests to
  make them pass; you may ADD a temporary reproduction script while working,
  but it must not appear in your final patch.
- Budget: aim to finish an instance within about 30 minutes. If you are
  stuck past that, save your best attempt and move on — a partial patch
  beats no patch.

## Producing the patch

From the target repository root, with your fix applied to the working tree:

    git add -A && git diff --cached <base_commit> > patch.diff

The patch must be a unified diff relative to the base commit, containing
only source-code changes (no reproduction scripts, no test edits).

## Recording the result

Back in THIS repo (the benchmark repo), on your work branch:

1. Save the patch to `bench2/results/<run_id>/<instance_id>.patch`.
2. Write `bench2/results/<run_id>/<instance_id>.meta.json`:

       {
         "instance_id": "<instance_id>",
         "started_at": "<UTC ISO timestamp when you began this instance>",
         "finished_at": "<UTC ISO timestamp when you saved the patch>",
         "self_assessment": "solved" | "partial" | "gave_up"
       }

3. Commit both files: `git commit -m "<run_id>: <instance_id>"` and push
   your branch. One commit per instance.

Your `<run_id>` and work branch are given in your kickoff prompt.

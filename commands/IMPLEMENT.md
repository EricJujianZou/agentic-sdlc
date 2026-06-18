---
name: implement-stage-command
description: Entry point for the implement stage — execute the latest plan, commit as you go.
read_when: Composed into the implement-stage prompt by the workflow; agents follow it verbatim.
sdlc_stage: implement
---

# /IMPLEMENT — implementer

You are a senior implementer. Execute the plan; do not re-plan. If the
plan is wrong, report `outcome: "failure"` with the reason so the loop
returns to the plan stage — that is cheaper than improvising.

**Headless rule.** You are running headless — no human will ever answer a
question, and anything you ask will go unread. If you hit a contradiction,
missing prerequisite, or any blocker, do not ask and do not stall: report
`outcome: "blocked"` in the status block (the only channel anyone reads),
with the reason in `failure_reason`. Never end your turn with a question.

1. Follow `commands/PRIME.md` first.
2. Read the latest plan output listed under "Prior stage outputs" in this
   prompt. That plan is your work order.
3. Read `stage_specs/implement_feat.md` for conventions and definition of
   done.
4. Implement step by step. Match the surrounding code's style. Run the
   build/quick checks the spec names as you go.
5. Commit everything before you finish (file edits are micro-committed
   for you; anything you created via Bash you must `git add` and commit
   yourself). A dirty tree fails the stage mechanically.
6. Append one short learnings entry to `progress.txt` if you discovered
   a reusable pattern or gotcha; keep the file under 100 lines.

End your reply with exactly this status block (JSON, last thing in the
message), with values filled in:

```json
{
  "stage": "implement",
  "ticket_id": "<your ticket id>",
  "outcome": "success | failure | blocked",
  "exit_signal": false,
  "summary": "one or two lines",
  "failure_reason": null,
  "files_changed": 0,
  "suggested_tools": [],
  "system_repair_suggested": false
}
```

`files_changed` must be the real count (`git diff --stat` against the
stage start). Reporting 0 changes repeatedly opens the circuit breaker.

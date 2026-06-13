---
name: history
description: One line per merged ticket (what + why), written by the workflow at merge time. Human-only durable record; agents never read this file.
read_when: Never, by agents. Humans browse it to see what the system has shipped.
sdlc_stage: none (written at merge gate)
---

# Merge history

<!-- The workflow appends one line per merged ticket: `- YYYY-MM-DD S-NNN: what + why` -->
- 2026-06-10 S-001: local static ticket dashboard (dashboard/) rendering prd.json by status, replacing Notion for viewing the backlog
- 2026-06-12 S-008: post-gate document stage: writes/commits docs/changes/<id>.md for the merge-gate human; built by the harness in 1 iteration (test_run2.md)

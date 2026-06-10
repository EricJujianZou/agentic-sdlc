# Claude Code Harness — Repo Library (MECE)

A deduplicated, mutually-exclusive / collectively-exhaustive list of the key repos
for building an autonomous Claude Code harness. Where multiple repos did the same
job, the most canonical / most-starred one was kept and the rest dropped.

| Repo | Primary purpose (one job) | Stars / signal | Use it when |
|---|---|---|---|
| **`hesreallyhim/awesome-claude-code`** | Master curated index (skills, hooks, commands, orchestrators) | The canonical "awesome" list | **Starting map** — browse before building anything; don't rebuild what exists |
| **`snarktank/ralph`** | Canonical autonomous SDLC loop (prd.json + progress.txt + git memory) | Reference impl of the Ralph pattern | You want the **clean architecture** to copy for autonomous build-to-completion |
| **`frankbria/ralph-claude-code`** | Production Ralph with safety engineering | 784 tests, dual exit-gate, rate limiting, circuit breaker | You're running Ralph **unattended** and need the guardrails |
| **`rohitg00/awesome-claude-code-toolkit`** | Largest component library (hooks / rules / agents / templates) | 135 agents, 35 skills, 20 hooks, 15 rules | You need **ready-made guardrail hooks** that physically block destructive git / edit loops |
| **`VoltAgent/awesome-claude-code-subagents`** | Subagent definition library (100+) | 100+ specialized, model-routed subagents | You're building your **generator / validator / specialist panel** |
| **`textcortex/claude-code-sandbox`** | Local Docker isolation for yolo-mode | Docker + browser terminal | You want to run `--dangerously-skip-permissions` **safely on Win11** (in a box) |
| **`rins_hooks`** | Cross-platform hooks installer | 101★, universal hooks + installer | You want a **portable hooks bundle** across machines / projects |

## Tie-break notes

- **Ralph variants:** ~6 forks exist. Rule of thumb:
  - `snarktank/ralph` → **learn the pattern** (cleanest reference)
  - `frankbria/ralph-claude-code` → **run it safely** (real guardrails)
  - Others (`open-ralph-wiggum`, `coleam00/ralph-loop-quickstart`, `harrymunro/ralph-wiggum`)
    are variants — only reach for them if you need their one specific feature
    (multi-model support, headless browser self-verification, etc.)
- **"Awesome" lists:** several exist (`jqueryscript`, `GetBindu`, `hesreallyhim`).
  `hesreallyhim/awesome-claude-code` kept as the canonical curated index; the others
  are supersets/dupes with lower curation.

## How the layers fit together

```
hesreallyhim/awesome-claude-code      <- map (find components)
        |
        v
snarktank/ralph                       <- loop architecture
frankbria/ralph-claude-code           <- + safety to run unattended
        |
        v
rohitg00 toolkit + rins_hooks         <- hooks/rules = hard guarantees
VoltAgent subagents                   <- generator/validator panel
        |
        v
textcortex/claude-code-sandbox        <- isolation box (Win11 yolo-safe)
```

## Reminder: the safety floor (applies regardless of repo)

- Always cap **max-iterations** + **rate limit** (the real safety net, not completion-promise strings)
- Output should always be a **PR into a sandbox branch**, never a merge or deploy to main
- Put hard guarantees in **hooks / deny rules**, not natural-language instructions
- Run unbounded / yolo loops only **inside a container or VM**, never on the bare host
- Never expose production credentials to the loop

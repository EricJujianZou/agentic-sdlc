---
name: safety-plan
description: P0 safety subsystem — exit gates, circuit breaker, rate/budget limits, branch policy, and isolation. Nothing runs unattended until this plan is implemented.
read_when: Building or modifying the orchestrator's loop control; investigating why a run was halted; before enabling any unattended/scheduled run.
sdlc_stage: build-time (harness development); enforced at every stage at runtime
---

# Safety Plan

The loop can never be unbounded. Every mechanism here is enforced by the **workflow (.py)**, not by prompt instructions.

## 1. Exit gates

- Every stage ends with a structured status block (schema in `plans/harness_plan.md`). The orchestrator parses it; **only the orchestrator declares a stage or ticket done.**
- Dual gate for ticket completion: explicit `exit_signal: true` in the status block AND acceptance criteria in `prd.json` verified by the test stage. Agent prose ("everything passes!") counts for nothing.

## 2. Circuit breaker

Workflow-level counters, checked after every stage:

| Condition | Default threshold | Action |
|---|---|---|
| Loops with no file changes | 3 | Open circuit |
| Loops with the same error | 5 | Open circuit |
| Sharp output decline vs. prior loops | >70% | Open circuit |
| Permission denials | 2 | Open circuit |
| Max iterations per ticket | configurable per workflow | Halt, mark ticket `blocked` |

Open circuit = halt the run, write the reason to `state.json`, cooldown (default 30 min) before any auto-retry. A blocked ticket requires human attention — the system must not silently retry forever.

## 3. Rate and budget limits

- Hourly API-call cap and per-ticket token/cost budget in `configs/budgets.json`.
- Detect the provider 5-hour usage limit and pause gracefully instead of erroring in a loop.
- Log per-stage token usage to `state.json` so budget enforcement is cheap.

## 4. Branch policy

- Agents work on `adw/<ticket-id>` branches only. **Pushing to main is denied by hook** (see `plans/hooks_plan.md`), not by instruction.
- Merge to main is a final gate: human one-click, or deterministic auto-merge only when all of (build, tests, review pass, budget not exceeded) hold.

## 5. Isolation

- Unattended runs execute in an isolated environment: a container, or at minimum a dedicated git worktree + OS user with deny-rules on destructive commands.
- No production or real credentials are ever exposed to the loop. Use scoped tokens with the narrowest possible permissions.
- `--dangerously-skip-permissions` is allowed **only inside the container**, never on the bare Win11 host.

## Reference repos — adopt before building

| Tool need | Repo | What to take |
|---|---|---|
| Circuit breaker, dual exit gates, rate limiting, usage-limit detection | `frankbria/ralph-claude-code` | Threshold design, `RALPH_STATUS` parsing, cooldown logic (`ralph_loop.sh`) |
| Docker isolation for skip-permissions mode | `textcortex/claude-code-sandbox` (**archived** — continued as **Spritz**) | Container + browser-terminal pattern; evaluate Spritz first |
| Official sandboxing | Docker's Claude Code sandbox docs; Claude Code native sandbox settings | Prefer official/native options over third-party if they cover the need |
| Destructive-command deny rules | `rohitg00/awesome-claude-code-toolkit` (hooks/) | Ready-made guardrail hooks that physically block destructive git/edit loops |

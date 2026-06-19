# agentic-sdlc

A harness that takes a human-written ticket and autonomously carries it
through **plan → implement → test → review**, then stops at a human merge
gate. Each SDLC stage runs as a **fresh headless Claude Code instance**;
all control flow lives in deterministic Python; git is the durable memory
layer. Built for personal projects, single developer, unattended runs that
are safe by construction.

Read `architecture.md` for the full design. This README is the operator's
manual: how a human runs it, what the knobs are, and what to expect.

## How it works in one diagram

```
prd.json ticket (passes: false)
   ↓
workflows/feat_full_cycle.py        ← deterministic orchestrator (you run this)
   ↓ per stage: plan → implement → test → review
fresh `claude -p` instance          ← scoped tools per stage, 15-min timeout
   ↓ reads commands/ + stage_specs/ + skills/
JSON status block                   ← the ONLY completion signal
   ↓
done → branch adw/<ticket-id> awaits YOUR merge   (never auto-merges to main)
fail → bounded loop back to plan (circuit breaker watching)
```

## Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/) (`uv sync` to set up)
- Claude Code CLI on PATH (`claude --version`)
- A git repo (this one) — agents work on `adw/<ticket-id>` branches

## Quick start

1. **Write a ticket.** Add a story to `prd.json` (humans curate the
   backlog in `task.md`, then promote tickets into `prd.json`):

   ```json
   {
     "id": "S-001",
     "type": "feat",
     "priority": 1,
     "title": "…",
     "description": "…",
     "acceptance_criteria": ["…", "…"],
     "skill_match": null,
     "passes": false,
     "status": "open"
   }
   ```

   `type` ∈ `feat | bug | chore | system-repair`. Decompose until one
   stage fits comfortably in one context window — spec quality is the
   highest-leverage variable in the system.

2. **Run the workflow:**

   ```powershell
   uv run python workflows/feat_full_cycle.py
   ```

3. **When it prints `S-001 done … ready for merge gate`,** review the
   `adw/S-001` branch and merge it yourself. The harness cannot and will
   not push or merge to main — a PreToolUse hook physically blocks it.

## Workflow flags

`workflows/feat_full_cycle.py` (currently the only workflow; `bug`/
`trivial` variants are planned — `plans/improvements.md` A3):

| Flag | Meaning | Default |
|---|---|---|
| `--ticket S-NNN` | Run a specific story | highest-priority `open` story with `passes: false` |
| `--max-iterations N` | Cap on plan→review loops | `max_iterations_default` in `configs/budgets.json` (5) |
| `--override-cooldown` | Start despite an active circuit-breaker cooldown | off — refusing is the default; overriding is a human judgment call |
| `--isolate` | Run each stage session inside a docker container (= `ADW_ISOLATION=1`); see [Container isolation](#container-isolation) | off — stages run on the host |

Exit code 0 = ticket done; 1 = blocked/halted (reason printed, also in
`state.json.last_failure`).

## Phone-facing backlog

File tickets from your phone as **GitHub Issues labeled `adw`** (one type
label — `feat`/`bug`/`chore`/`system-repair` — plus an optional `p<N>`
priority). A terse one-liner is fine: the decompose stage expands it into
acceptance criteria, and quote-bar/markdown noise from a phone paste is
tolerated. As a ticket runs, it comments each stage transition back on the
source issue (and opens a PR when done), so your phone gets a running log.

- **Pull tickets in:** `uv run python workflows/sync_issues.py`
- **Pull, then work the backlog in one pass:**
  `uv run python workflows/poll_once.py [--max-tickets N]`

`poll_once.py` is one launch = one pass: it syncs, then works the open backlog
(honoring the circuit-breaker cooldown and `--max-tickets`, stopping on the
first blocked/halted ticket). It is **not** a daemon — there is no loop or
timer. For periodic pickup, point an OS scheduler at it on an always-on
machine; that wiring is a human opt-in, outside the harness's authority:

- **Windows Task Scheduler:** create a Basic Task on your interval whose
  action runs `uv run python workflows/poll_once.py` in the repo directory.
- **cron (Linux/macOS or a VM):**
  `*/30 * * * * cd /path/to/repo && uv run python workflows/poll_once.py`

## Configuration

| File | Knobs |
|---|---|
| `configs/budgets.json` | max iterations (5), per-ticket token budget (2M), stage timeout (15 min), circuit cooldown (30 min) |
| `configs/models.json` | model per stage — opus for plan/review/decompose, sonnet for implement/test, haiku for trivial |
| `.claude/settings.json` | hook wiring (don't remove; the hooks are the hard guarantees) |

By default the harness operates on its own repo. To build a *different* repo,
set `ADW_REPO=/path/to/project` (or run from inside it): `prd.json`, state,
git, and run logs resolve against that target while prompts/configs default to
the engine. See `docs/using-on-another-repo.md` for the `.adw/` skeleton.

## Safety model (what protects you during unattended runs)

- **Hooks are law** (`hooks/`): `pretooluse_guard.py` denies force-push,
  any push/merge to main, history rewrites, `--no-verify`, `rm -rf`
  outside the worktree, and — during harness runs — any edit to harness
  files without an approved system-repair ticket. `stop_checklist.py`
  and `posttooluse_autocommit.py` enforce clean hand-offs.
- **Circuit breaker** (`adw/safety.py`): opens on 3 no-change implement
  loops, 5 identical errors, ≥2 permission denials, >70% output decline,
  token-budget breach, or a provider usage-limit signal. Opening writes a
  30-minute cooldown into `state.json` that blocks auto-retries.
- **Dual exit gate**: a ticket is done only when the review stage reports
  `outcome: success` **and** `exit_signal: true` in its JSON status
  block. Agent prose counts for nothing.
- **Merge to main is human-only.** Always.

FYIs / sharp edges:

- The guard hook blocks *your* pushes to main too when you run git
  through an agent session — push from a plain terminal, or via PR
  (`gh pr create` + `gh pr merge`).
- Known quirk: the push-to-main regex can false-positive on branch names
  containing the word `main` (see `plans/improvements.md` A4).
- Stage agents get scoped tools only (plan is read-only; implement gets
  Edit/Write/Bash; PowerShell is deliberately not in scope on any stage).
- Runs assume the safety floor in `claude-code-harness-repos.md`: never
  expose production credentials to the loop; prefer container isolation
  for fully unattended operation (see [Container isolation](#container-isolation)).

## Container isolation

By default stages run on the bare host. For unattended operation the safety
floor (`plans/safety_plan.md` §5) wants each stage session confined to a
container: the host filesystem outside the repo is unreachable, no host
credentials cross the boundary beyond a scoped git token (and the API key
the CLI needs), and `--dangerously-skip-permissions` becomes defensible
because it is contained.

**Enable it** with `--isolate` (or `ADW_ISOLATION=1`). When on, `adw/invoke.py`
wraps the same `claude -p …` argv in `docker run` (`adw/isolation.py`);
when off, the host path runs exactly as before — that is the documented
fallback, and the full test suite exercises the off path.

**Setup (one time):**

```bash
# 1. Build the sandbox image (toolchain only; the repo is mounted, not copied):
docker build -t adw-sandbox:latest -f docker/Dockerfile .

# 2. Give the container its own scoped credentials (never the host's):
export ANTHROPIC_API_KEY=sk-...        # a key scoped to this use
export ADW_GIT_TOKEN=ghp_...           # a PAT with push to this repo only

# 3. Run a ticket with stages isolated:
uv run python workflows/feat_full_cycle.py --ticket S-NNN --isolate
```

At run time `adw` mounts only the repo at `/workspace` (`--mount`, so Windows
paths parse), sets `--workdir /workspace`, and forwards **only**
`ADW_TICKET_RUN`/`ADW_STAGE` plus the allowlisted secrets above via `-e NAME`
(by name, so values never land in the argv). The host credential store,
`~/.claude` session, and `~/.gitconfig` are never mounted. Hooks keep working
because `.claude/settings.json` and `hooks/*.py` live in the mounted repo and
the image carries `uv`/python/git. Knobs: `ADW_SANDBOX_IMAGE` (default
`adw-sandbox:latest`), `ADW_SANDBOX_NETWORK` (default `bridge`), `ADW_DOCKER_BIN`
(default `docker`).

**Limits (read before trusting it):**

- **Verify the live container by hand.** The offline test suite only asserts
  the shape of the `docker run` argv and the on/off dispatch — it cannot run a
  container. Confirm real isolation on your host: that a stage cannot read a
  file outside the repo, that `printenv` inside shows no host secrets beyond
  the two above, and that the autocommit/guard/stop hooks fire in-container.
- **Network is bridged egress, not an allowlist.** `bridge` permits any
  outbound connection (needed for `api.anthropic.com` and `github.com`).
  Restricting egress to just those hosts (a proxy or `--network` policy) is a
  follow-up, not delivered here.
- **In-container CLI auth is your responsibility.** The image ships no
  credentials; if `ANTHROPIC_API_KEY` is unset the stage will fail to
  authenticate inside the container.
- **Docker Desktop must be running.** With the daemon down, `--isolate` fails
  at `docker run`; the host fallback (omit the flag) always works.

## CI gate and branch protection

The in-loop test and review stages are produced by the same agents that
wrote the code — they sit *inside* the harness's trust boundary. The CI
gate (`.github/workflows/ci.yml`, S-009) runs `uv run pytest -q` on every
pull request to `main` in GitHub's environment, where no stage agent can
skip, fake, or misreport it. It is the **agent-proof** half of the safety
model and the precondition that makes auto-merge defensible (the in-harness
mirror is S-010 / `plans/improvements.md` C3).

The workflow file alone does not *enforce* anything — GitHub will still let
a red PR merge until you turn on branch protection. That is a one-time
manual repo-admin step (agents cannot change repo settings or push to
`main`, by design), so do it once from a plain terminal:

**GitHub UI:** Settings → Branches → add a ruleset (or classic protection
rule) for `main` → "Require status checks to pass" → select the CI check
(it appears as `test`, the job name; rulesets may show it as `CI / test`) →
save.

**`gh` CLI** (run from a plain terminal, not an agent session):

```bash
gh api -X PUT repos/EricJujianZou/agentic-sdlc/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["test"] },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

The check context only exists after the workflow's first run, so open one
PR (this gives the check a name), then enable protection selecting that
name. Once enabled, `main` rejects any merge whose CI check is not green —
the single deterministic gate that protects you when no human reads the
diff.

## Repository map

| Path | What it is | Humans edit? |
|---|---|---|
| `task.md` | Human-curated ticket backlog (promote into `prd.json` to run) | yes |
| `prd.json` | Machine ticket store the orchestrator picks from | yes (schema-validated) |
| `workflows/` | Deterministic orchestrators — the things you run | yes |
| `adw/` | Harness library: orchestrator, invocation, safety, tickets, state, runlog | yes (agents: only via system-repair ticket) |
| `commands/` | Stage entry prompts (PRIME, PLAN, IMPLEMENT, TEST, REVIEW) | yes |
| `stage_specs/` | Per-stage, per-ticket-type contracts | yes |
| `skills/` | Cached solutions to problem classes (empty in v1; seeded over time) | yes |
| `hooks/` | PreToolUse/PostToolUse/Stop guarantees | yes |
| `configs/` | Budgets and model routing | yes |
| `plans/` | Design docs per subsystem + `improvements.md` | yes |
| `observability/runs/<id>/` | Per-run logs and stage hand-offs (gitignored, deleted post-run) | no |
| `observability/history.md` | One line per merged ticket, human-only | no |
| `progress.txt` | Agent tactical learnings, hard-capped at 100 lines | prune |
| `state.json` | Current ticket/stage/iteration (gitignored, transient) | no |
| `AGENTS.md` | Mandatory orientation every spawned agent reads first | yes |
| `architecture.md` | System design | yes |

## Skills

`skills/` holds generalized solutions to *classes* of problems in Claude
Code Skills format (front-matter always discoverable, body read on
demand). Tickets opt in via `skill_match`. None exist yet; they get
created by humans (or approved system-repair tickets) when a ticket
class has been solved cleanly once — see `skills/README.md` for the
graduation path. Never write a skill from theory; generalize from a
shipped ticket.

## Testing the harness itself

```powershell
uv run pytest -q        # ~94 tests, fast, no network
```

The test suite covers the orchestrator loop, status-block parsing,
circuit breaker, hooks, tickets schema, and prompt assets.

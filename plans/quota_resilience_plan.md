---
name: quota-resilience-plan
description: Three follow-up fixes surfaced by the 2026-06-19/20 quotad dogfood — real session-limit detection + reset parsing (the format S-015 was built against was a guess), the observer wiping cooldown on non-quota halts, and the scheduled task capturing no output. Feeds S-018/019/020.
read_when: Filing or building the post-quotad resilience tickets; investigating a misclassified quota halt, a vanished cooldown, or an opaque scheduled-task run.
sdlc_stage: build-time (harness development); enforced at runtime
---

# Quota-Resilience Plan (S-015 follow-ups)

The quotad work (S-015) made a quota interruption a first-class, auto-resumable
state. Dogfooding it overnight against the **real** Claude subscription proved
the feature was built against a *guessed* message format and never fires on the
actual one, and surfaced two adjacent defects. This plan turns all three into
runnable system-repair tickets.

Ground truth captured 2026-06-20 (the real CLI subscription limit message):

```
You've hit your session limit · resets 1:10am (America/Toronto)
```

Verified against live code: `detect_usage_limit()` → **False** on this string
("session limit" is uncovered), and `_parse_usage_reset()` → **None** ("resets
1:10am (America/Toronto)" is neither a Unix epoch nor ISO-8601). So S-015's
detector misses the real limit and its cooldown falls back to the default;
during the dogfood this made S-017's plan stage hit the session limit and get
**misclassified** as `output declined >70% (7193→63 chars)`.

| Task | Ticket | Severity | Effort |
|---|---|---|---|
| A. Recognize + parse the real session-limit message | S-018 | P1 (makes quotad actually work) | M |
| B. Observer must not wipe the run's cooldown | S-019 | P2 (latent correctness) | S |
| C. Scheduled poll pass must be auditable | S-020 | P2 (observability) | S |

All three are `type: system-repair` (they edit harness files, so the guard hook
requires that type). Sequence A → re-run S-017 → B → C; A is the only one that
must land before unattended overnight operation can be trusted.

---

## Task A — Recognize and parse the real session-limit message (S-018)

### Problem
`adw/safety.py` `_USAGE_LIMIT_PATTERNS` covers `rate_limit_event`, "5-hour
limit", "usage limit reached", "out of extra usage" — all guesses. The real
subscription message is `You've hit your session limit · resets <h:mm><am/pm>
(<IANA tz>)`. Neither detection nor reset-parsing handles it, so:
- the quotad path never triggers on a real session limit, and
- a session limit hit mid-run is misread as an output-decline halt (S-017).

### Fix (files: `adw/safety.py`, `pyproject.toml`, `tests/test_safety.py`)
1. **Detection.** Add a `session limit` pattern to `_USAGE_LIMIT_PATTERNS`
   (e.g. `re.compile(r"\bsession limit\b", re.IGNORECASE)`). Safe against prose
   false-positives because detection is already gated on a *non-successful*
   stage (the 2026-06-19 hand-fix in `_evaluate`).
2. **Reset parsing.** Extend `_parse_usage_reset` with a clause matcher for
   `reset[s] <hour>[:<min>] <am|pm> (<tz>)`:
   - Compute the next **future** wall-clock instant of that time in the named
     IANA zone via `zoneinfo.ZoneInfo(tz)`; if it has already passed today,
     roll to tomorrow (session resets are <~5h away, so "next occurrence" is
     correct). Return it as UTC.
   - On any failure (unknown tz, unparseable) return `None` → the existing
     `usage_limit_cooldown_minutes` fallback applies. Never raise.
3. **Windows tz data.** `zoneinfo` has **no** tz database on Windows; add
   `tzdata` to `pyproject.toml` dependencies (and `uv.lock`), or
   `ZoneInfo("America/Toronto")` raises `ZoneInfoNotFoundError`. Keep the
   try/except fallback regardless, so a missing tz never breaks a run.
4. The keep-vs-drop call on the older guessed patterns: **keep** them (they are
   plausible real forms for API-billing / extra-usage) and simply add the
   session-limit one.

### Acceptance criteria (S-018)
- `detect_usage_limit("You've hit your session limit · resets 1:10am (America/Toronto)")` returns `True`; the existing four patterns still match their samples; benign prose ("all tests passed, no limits") still returns `False`.
- `_parse_usage_reset` returns the correct future UTC instant for `resets 1:10am (America/Toronto)` given a frozen `now`, and rolls to the next day when that time has already passed; it returns `None` (not an exception) for an unknown timezone or a clause with no parseable time, so the configured `usage_limit_cooldown_minutes` fallback still governs.
- A real session limit hit by a stage (non-success, message in output/stderr) routes through the quotad path (`USAGE_LIMIT_HALT_REASON` / `quotad` outcome), not the output-decline or dead-on-arrival rules.
- `tzdata` is a declared dependency so timezone resolution works on Windows; if it is ever absent, reset parsing degrades to `None` rather than raising.
- Unit tests cover detection of the real message, reset parse (frozen now, same-day-passed roll, unknown-tz `None`), and that a session-limit stage result yields the quotad outcome.
- Full suite `uv run pytest -q` stays green.

### Follow-on action (not a code change)
Re-run **S-017** after S-018 lands. Its halt was solely this misclassified
session limit, not a design failure of the mid-ticket-checkpoint work; a clean
re-run should let it complete (then review the orchestrator changes by hand
before merge, since S-017 touches the core `run_ticket` invariant).

---

## Task B — Observer must not wipe the run's cooldown (S-019)

### Problem
`adw/orchestrator.py` `run_observer` does `state = State(ticket_id=..., stage=
"observe"); save_state(state, state_path)`. A fresh `State` has
`cooldown_until=None`, so when the observer runs after a halt (it runs on every
non-`done` outcome) it **overwrites** the cooldown the breaker just set. Evidence:
after S-017's halt, `state.json` showed `cooldown_until: null` despite the halt
having opened the circuit. It was harmless overnight only because no open
stories remained; in general it lets an auto-retry start before the cooldown
elapses — defeating the breaker's pause.

### Fix (files: `adw/orchestrator.py`, `tests/test_orchestrator.py`)
`run_observer` should preserve the prior run's cooldown when it writes the
transient observe-state: load the existing `state.json` (if present) and carry
forward `cooldown_until` (the observer only needs `ticket_id`, `stage=observe`,
and `last_failure` for its prompt/hook context). Equivalent acceptable approach:
write the observe-state to a side path and never touch the run's `state.json`.
Note S-015 already side-steps this for the quotad path (it skips the observer),
so this fixes every *other* halt (decline, same-error, instant-failure, budget).

### Acceptance criteria (S-019)
- After a halt that set `cooldown_until`, running the observer leaves `cooldown_until` intact in `state.json` (unchanged value), while still presenting the failure reason to the observer stage.
- `check_cooldown` therefore still reports an active cooldown after the observer has run on a non-quota halt.
- The quotad path (observer skipped) is unaffected; decompose's pre-work state write is unaffected (no cooldown exists yet there).
- Unit tests with a fake invoke_fn cover: cooldown survives an observer run; observer still receives `last_failure`.
- Full suite `uv run pytest -q` stays green.

## Task C — Scheduled poll pass must be auditable (S-020)

### Problem
The registered `\ADW\ADW` task runs `uv.exe run python workflows/poll_once.py
--max-tickets 1` with **no output redirection**, so nothing is captured. That is
why a 22:35 run that took 29 minutes (committed nothing, exited 0) is
unexplainable after the fact. `register-poll-task.ps1` *intends* a
`%LOCALAPPDATA%\adw\poll.log` redirect via a `cmd /c` wrapper, but the live task
lacks it (registered by a different path). Relying on a shell redirect is also
fragile.

### Fix (files: `workflows/poll_once.py`, `README.md`; optionally re-run `scripts/register-poll-task.ps1`)
Make `poll_once` **self-log**, independent of how the task is registered: append
one timestamped line per pass to a log outside the repo (default
`%LOCALAPPDATA%/adw/poll.log`, overridable by `--log-path` / env), recording
start time, sync result (+N synced / skipped), tickets run, and the stop reason
— including a clear line when a pass spends real time (so a future long run is
explained). Keep it outside the repo so it never dirties the working tree.
Document re-registering the task via the script (which adds its own redirect) as
the human/admin step that also restores least-surprise; note the live task could
not be modified non-elevated (ACL on `\ADW\`).

### Acceptance criteria (S-020)
- `poll_once` appends a single, bounded, timestamped summary line per invocation to a log path outside the target repo (default under `%LOCALAPPDATA%/adw`, overridable), covering sync outcome, tickets run, and stop reason; a failure to write the log is swallowed and never affects the pass.
- The log path is configurable and the working tree is never touched (no new tracked/untracked files in the repo).
- README documents the self-log and the one-time admin re-registration of the scheduled task for redirected stdout, labeling task modification an out-of-agent-scope human action.
- Unit tests cover the summary-line content for a synced/ran pass and a stop-before-backlog pass, with the log path injected (no real scheduler).
- Full suite `uv run pytest -q` stays green.

---

## Sequencing, dogfood notes, and risks

- **Order:** S-018 first (unblocks correct quota handling) → re-run S-017 →
  S-019 → S-020. Only S-018 gates trustworthy unattended overnight runs.
- **Dogfood isolation:** the `\ADW\ADW` task fires hourly and cannot be disabled
  without admin. Park new tickets out of its pick set (status ≠ `open`) and run
  them by explicit id, as in the 2026-06-19 attended dogfood, so the scheduler
  never races the manual run for the working tree.
- **Risks:** (1) S-018 adds a dependency (`tzdata`) — an implement stage editing
  `pyproject.toml` then `uv sync` can be flaky mid-dogfood; consider adding the
  dep by hand before dogfooding S-018. (2) The 29-min historical run stays
  unexplained (no log existed); S-020 only prevents recurrence. (3) S-017's
  re-run still changes the core `run_ticket` loop — hand-review before merge.
- **These become** `S-018` / `S-019` / `S-020` in `prd.json` (mirror this plan's
  AC), filed `system-repair`, `status: open` so the backlog runner picks them.

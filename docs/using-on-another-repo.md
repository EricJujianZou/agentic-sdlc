# Using the harness on another repo

The harness (the "engine") can build *any* repo, not just itself. The engine
stays where it is; your project repo (the "target") carries only a tiny
`.adw/` skeleton — no harness code is copied. Path resolution lives in
`adw/paths.py`: with `ADW_REPO` set, `prd.json`, `state.json`, run logs, git
branches/commits, and `.claude/` all resolve against the target, while prompt
and config assets default to the engine (overridable per project).

## One-time setup of a target repo

From the root of your project repo:

### 1. Create the backlog — `prd.json`

```json
{
  "project": "my-project",
  "stories": []
}
```

Add stories by hand (schema in `plans/tickets_plan.md`) or let
`workflows/sync_issues.py` populate it from GitHub Issues labeled `adw`.

### 2. (Optional) Override engine configs — `.adw/configs/`

By default the target uses the engine's `configs/models.json` and
`configs/budgets.json`. To override either, create `.adw/configs/` in the
target with your own copy; a present `.adw/configs` (or `.adw/commands`) wins
over the engine's. Omit it to inherit the engine defaults.

### 3. Wire the hooks — `.claude/settings.json`

The hooks (`pretooluse_guard.py`, `stop_checklist.py`,
`posttooluse_autocommit.py`) are the hard safety guarantees, and they live in
the **engine**. A stage runs with the target as its working directory, so the
target's `.claude/settings.json` must point at the engine's hooks by absolute
path. Copy this into the target's `.claude/settings.json`, replacing
`<ENGINE>` with the absolute path to your engine checkout:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|PowerShell", "hooks": [
        { "type": "command", "command": "uv run --quiet python <ENGINE>/hooks/pretooluse_guard.py" } ] },
      { "matcher": "Edit|Write|NotebookEdit", "hooks": [
        { "type": "command", "command": "uv run --quiet python <ENGINE>/hooks/pretooluse_guard.py" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|NotebookEdit", "hooks": [
        { "type": "command", "command": "uv run --quiet python <ENGINE>/hooks/posttooluse_autocommit.py" } ] }
    ],
    "Stop": [
      { "hooks": [
        { "type": "command", "command": "uv run --quiet python <ENGINE>/hooks/stop_checklist.py" } ] }
    ]
  }
}
```

## Running

Point `ADW_REPO` at the target and invoke an engine workflow:

```bash
ADW_REPO=/path/to/my-project uv run --project /path/to/engine \
  python /path/to/engine/workflows/feat_full_cycle.py --ticket S-001
```

On **PowerShell** the inline `ADW_REPO=… <cmd>` form does nothing (it isn't a
prefix-assignment shell) — set the env var on its own line first, then run:

```powershell
$env:ADW_REPO = "C:/path/to/my-project"
uv run --project C:/path/to/engine `
  python C:/path/to/engine/workflows/poll_once.py --max-tickets 1
Remove-Item Env:\ADW_REPO   # clear afterwards so it doesn't leak into later commands
```

Everything lands in the target: the `adw/S-001` branch, the commits, the run
logs under `my-project/observability/runs/`, and the `prd.json` status flips.
The engine repo is never touched. With `ADW_REPO` unset and the command run
from inside the engine, the harness self-hosts exactly as before.

## Limits (this is the core indirection, not the finished product)

- **Hooks need the engine's absolute path** in the target's
  `.claude/settings.json` (above). A packaged install (`uv tool install`,
  deferred S-011 follow-up) would resolve hooks automatically; until then this
  is a manual one-line-per-hook edit.
- **`stage_specs/` resolve from the engine.** Stage command files may
  reference `stage_specs/<stage>_feat.md`; those are read from the engine. If
  you override `.adw/commands`, mirror any `stage_specs` they depend on.
- **Merge to main stays a human gate** in the target repo, unchanged.
- **`uv run --project <engine>`** (or an activated engine venv) is how the
  engine's dependencies are found while operating in the target.

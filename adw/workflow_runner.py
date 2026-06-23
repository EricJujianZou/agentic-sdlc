"""Shared workflow orchestration: the outer setup every adw workflow needs.

The feat/bug/trivial workflows differ only in their stage order; everything
else — the cooldown gate, config loading, story selection, work branch,
prompt composition, invoke wiring, and outcome bookkeeping — is identical
and lives here so the entry-point scripts in workflows/ stay thin and never
triplicate orchestration (architecture.md principle 1). Each workflow script
owns its stage order and passes it in; this module never decides it. The
backlog runner (workflows/run_backlog.py) reuses the same per-story core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from adw import isolation, paths, runlog, worktrees
from adw.github import (
    GitHubError,
    add_labels,
    comment_on_issue,
    create_issue,
    engine_repo_slug,
    get_token,
    list_open_issues,
    open_or_update_pr,
    outcome_comment_body,
    pr_body,
    remove_label,
    repo_slug,
    source_issue_number,
)
from adw.invoke import invoke_stage
from adw.orchestrator import (
    STAGE_ORDER,
    ObserverResult,
    TicketOutcome,
    run_decompose,
    run_observer,
    run_ticket,
)
from adw.safety import CircuitBreaker, SafetyConfig, check_cooldown
from adw.state import load_state, State
from adw.status import parse_status_block, StatusBlockError
from adw.tickets import (
    Story,
    get_story,
    load_prd,
    mark_story,
    pick_next_stories,
    pick_next_story,
    reclaim_stale_in_progress,
    save_prd,
)

# All repo paths resolve through adw/paths.py: prd.json/state.json/git/runs
# land in the *target* repo (ADW_REPO, else the engine for self-hosting),
# while commands/ and configs/ default to the engine. Resolved at call time so
# a process honoring ADW_REPO operates entirely on the target.

# Which stage pipeline each ticket type runs; the backlog runner dispatches
# on this. feat/system-repair get the full cycle, bug skips review, chore
# skips planning. Mirrors the STAGE_ORDER each workflow script declares.
STAGE_ORDER_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feat": STAGE_ORDER,
    "system-repair": STAGE_ORDER,
    "bug": ("plan", "implement", "test"),
    "chore": ("implement", "test"),
}


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=paths.target_root(), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _ref_exists(ref: str) -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=paths.target_root(), capture_output=True, text=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _new_branch_base() -> str | None:
    if "origin" in _git("remote").split():
        try:
            _git("fetch", "--quiet", "origin", "main")
        except subprocess.CalledProcessError:
            pass
    for candidate in ("origin/main", "main"):
        if _ref_exists(candidate):
            return candidate
    return None


def _snapshot_tracked_dirty() -> dict[str, bytes]:
    # `_git()` strips the whole output, which would eat the leading status
    # space of the first porcelain line and shift its fixed-column parse —
    # call subprocess directly here so column offsets stay accurate.
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=paths.target_root(), capture_output=True, text=True, check=True,
    )
    snapshot: dict[str, bytes] = {}
    for line in proc.stdout.splitlines():
        status, rel = line[:2], line[3:]
        if "D" in status:
            continue
        if "->" in rel:
            rel = rel.split("->", 1)[1].strip()
        path = paths.target_root() / rel
        if path.is_file():
            snapshot[rel] = path.read_bytes()
    return snapshot


def _ensure_work_branch(branch: str) -> None:
    if _git("branch", "--list", branch):
        # GH-46: sync may have left an uncommitted prd.json write on the
        # current branch; commit it before switching so checkout doesn't
        # abort on a dirty tree that would be overwritten.
        _commit_bookkeeping("chore: persist sync before resuming work branch")
        _git("checkout", branch)
    else:
        # GH-58: cut new branches from a clean base (origin/main, else main)
        # rather than current HEAD, which may be a previous/dead ticket
        # branch left behind by an interrupted run. `checkout -f -b` never
        # aborts on a dirty tree, so any uncommitted sync write (e.g. a
        # fresh prd.json) is snapshotted first and restored after, landing
        # as an uncommitted change on the new branch for `_mark_in_progress`
        # to pick up and commit.
        base = _new_branch_base()
        if base is None:
            _git("checkout", "-b", branch)
        else:
            dirty = _snapshot_tracked_dirty()
            _git("checkout", "-f", "-b", branch, base)
            for rel, data in dirty.items():
                (paths.target_root() / rel).write_bytes(data)


def _commit_bookkeeping(message: str) -> None:
    """Commit orchestrator state changes (prd.json status flips) so stages
    start from a clean tree — read-only stages cannot commit them, and the
    Stop checklist fails any stage that leaves a dirty tree."""
    if _git("status", "--porcelain").strip():
        _git("add", "-A")
        _git("commit", "-m", message)


def reap_stale_in_progress(
    *, stale_seconds: float, prd_path: str | Path | None = None,
    state_path: str | Path | None = None,
) -> list[str]:
    """Flip every stranded `in_progress` story back to `open` (GH-47): an
    interrupted run (machine sleep, killed agent, a concurrent tree op) leaves
    a ticket `in_progress` forever since `pick_next_story` never re-picks it.
    `state.json` is gitignored, so its mtime is a heartbeat git never disturbs,
    and `save_state` rewrites it at every stage entry — a ticket is "live"
    only if `state.json` names it AND was touched within `stale_seconds`.
    Commits the flip (if any) so the tree stays clean for the next stage."""
    prd_path = paths.prd_path() if prd_path is None else Path(prd_path)
    state_path = paths.state_path() if state_path is None else Path(state_path)
    ticket_id: str | None = None
    age: float | None = None
    try:
        ticket_id = load_state(state_path).ticket_id
        age = time.time() - state_path.stat().st_mtime
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        pass
    prd = load_prd(prd_path)
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=stale_seconds, live_ticket_id=ticket_id, state_age_seconds=age,
    )
    if reclaimed:
        save_prd(prd, prd_path)
        _commit_bookkeeping(f"chore: reclaim stale in_progress: {', '.join(reclaimed)}")
    return reclaimed


def _make_verify_fn(budgets: dict, cwd: str | Path | None = None):
    """Build the deterministic test-evidence runner the orchestrator calls
    after the dual gate (improvements C3). Command and timeout are budgets
    knobs; a non-zero exit or a timeout counts as 'not verified', so a
    failing tree can never be accepted as done.

    `cwd` is where the suite runs: the target repo by default, but a parallel
    worker passes its worktree dir so the re-run exercises the worktree's
    changes, not the pristine main tree (#4). Resolved at call time so an
    unset cwd still honors ADW_REPO."""
    command = budgets.get("test_evidence_command") or ["uv", "run", "pytest", "-q"]
    timeout_seconds = budgets.get("test_evidence_timeout_minutes", 10) * 60

    def verify() -> tuple[bool, str]:
        run_cwd = cwd if cwd is not None else paths.target_root()
        try:
            proc = subprocess.run(
                command, cwd=run_cwd, capture_output=True, text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return False, f"test-evidence run timed out after {timeout_seconds}s"
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            # On green, surface the pass count (e.g. "209 passed") so the
            # outcome comment can report a deterministic number to cross-check
            # against CI. Absent a parseable count, success still returns "".
            m = re.search(r"\d+ passed(?:, \d+ \w+)*", output)
            return True, (m.group(0) if m else "")
        detail = output.strip()
        return False, detail[-800:] if detail else f"pytest exited {proc.returncode}"

    return verify


def _push_branch(branch: str) -> bool:
    """Push `branch` to origin; degrade (print, return False) on any failure
    so a missing remote or offline credential never affects ticket outcome."""
    try:
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=paths.target_root(), capture_output=True, text=True, check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"github notify: push of {branch} failed, continuing without it: {exc}")
        return False


def _pr_title(story: Story) -> str:
    """`<id>: <title>`, without doubling the id when the stored title already
    carries it (e.g. a story synced before the sync-side prefix strip)."""
    title = story.title.strip()
    prefix = f"{story.id}:"
    if title.lower().startswith(prefix.lower()):
        title = title[len(prefix):].strip()
    return f"{story.id}: {title}"


def _notify_github(
    story: Story,
    outcome: str,
    reason: str = "",
    test_evidence: str | None = None,
    pr_description: str | None = None,
) -> None:
    """Best-effort outbound notification: push the work branch, open/update a
    PR for it, and comment the outcome on the source issue if one exists.
    Never raises — any GitHub/credential failure is printed and swallowed so
    a `done` ticket can never be turned into a failure by notification."""
    branch = f"adw/{story.id}"
    _push_branch(branch)
    try:
        token = get_token()
        owner, repo = repo_slug()
        open_or_update_pr(
            owner, repo, token,
            head=branch, base="main",
            title=_pr_title(story),
            body=pr_body(story, outcome, pr_description),
        )
        issue_number = source_issue_number(story.id)
        if issue_number is not None:
            comment_on_issue(
                owner, repo, token, issue_number,
                outcome_comment_body(story, outcome, reason, test_evidence),
            )
    except GitHubError as exc:
        print(f"github notify skipped: {exc}")


# Issue-state labels (S-014 follow-up). GitHub's only native issue state is
# open/closed, so "in progress" is expressed as a label: the issue stays OPEN
# while it runs and after it's done (the PR's "Closes #N" closes it on merge —
# the human gate), but its label tells the phone what state it's in, so a
# backlog of issues no longer all look identical.
RUN_LABEL_IN_PROGRESS = "in-progress"
RUN_LABEL_DONE = "done"
RUN_LABEL_BLOCKED = "blocked"
RUN_LABEL_QUOTAD = "quotad"

# Stage labels (S-016): a mutually-exclusive "currently in stage X" label so a
# GitHub Projects board can show Plan/Do/Check/Review-gate columns without any
# new frontend. The previous stage label is removed when the next is added.
STAGE_LABEL_PREFIX = "stage:"


def _set_run_label(story: Story, *, add: tuple[str, ...] = (), remove: tuple[str, ...] = ()) -> None:
    """Best-effort issue relabel so a phone-filed ticket shows its run state.
    No-op for plain S-NNN stories (no source issue). Never raises — like every
    other outbound notification, a GitHub/credential failure is swallowed so it
    can never change the ticket's outcome."""
    number = source_issue_number(story.id)
    if number is None:
        return
    try:
        token = get_token()
        owner, repo = repo_slug()
        for label in remove:
            remove_label(owner, repo, token, number, label)
        if add:
            add_labels(owner, repo, token, number, list(add))
    except GitHubError as exc:
        print(f"issue relabel skipped: {exc}")


# Observer (self-heal lens) labels. A non-done ticket gets ONE of these so the
# phone can tell, at a glance, whether the human should look at the harness or
# at the ticket itself.
SELF_HEAL_LABEL = "self-heal-suggested"   # harness-level: a system-repair is proposed
CLARIFY_LABEL = "needs-clarification"     # ticket-level: refine the ticket and re-run


def _post_observer(number: int, body: str, label: str) -> None:
    """Best-effort: comment the observer's verdict on the issue and add a label.
    Never raises — a notification failure can't change the ticket's outcome."""
    try:
        token = get_token()
        owner, repo = repo_slug()
        comment_on_issue(owner, repo, token, number, body)
        add_labels(owner, repo, token, number, [label])
    except GitHubError as exc:
        print(f"observer comment skipped: {exc}")


def _format_repair_comment(story: Story, result: ObserverResult) -> str:
    """Render a harness-level diagnosis as a ready-to-file system-repair ticket
    (human-gated): the human reviews and files/opens it if they agree."""
    r = result.repair or {}
    lines = [
        f"🩺 `{story.id}` observer — **harness-level**: {result.summary}",
        "",
        "A harness defect may have caused this. Proposed system-repair ticket "
        "(human-gated — review, then file/open if you agree):",
        "",
        f"**{r.get('title') or 'system-repair'}**",
    ]
    if r.get("description"):
        lines += ["", str(r["description"])]
    evidence = [e for e in (r.get("evidence") or []) if isinstance(e, str) and e.strip()]
    if evidence:
        lines += ["", "Acceptance criteria:"]
        lines += [f"- {e}" for e in evidence]
    return "\n".join(lines)


_FINGERPRINT_MARKER = "<!-- adw-upstream-fingerprint: {} -->"


def _repair_fingerprint(story: Story, result: ObserverResult) -> str:
    """A stable-ish dedup key for a harness-level finding: normalize the
    repair's title (or summary/ticket id as fallbacks) before hashing, so
    re-runs of the same underlying bug collapse to one upstream issue."""
    r = result.repair or {}
    basis = (r.get("title") or result.summary or story.id).strip().lower()
    return hashlib.sha256(basis.encode()).hexdigest()[:12]


def _format_upstream_issue(story: Story, result: ObserverResult, fingerprint: str) -> tuple[str, str]:
    """Render a harness-level finding as a standalone engine-repo issue
    (cross-repo routing): reuses the same body as the in-repo comment, plus a
    hidden marker the dedup check looks for on re-runs."""
    r = result.repair or {}
    title = f"system-repair: {r.get('title') or result.summary or story.id}"
    body = _format_repair_comment(story, result) + f"\n\n{_FINGERPRINT_MARKER.format(fingerprint)}"
    return title, body


def _file_upstream_repair(story: Story, result: ObserverResult) -> None:
    """Best-effort: file the harness-level finding as a system-repair issue in
    the *engine* repo when this run is cross-repo (a downstream user building
    their own target repo) — the engine owner otherwise never sees a bug their
    own self-hosting can't surface. Self-hosted runs (target == engine) are a
    no-op: today's in-repo comment already reaches the same place.

    Never raises: any GitHub/credential failure (including a missing token
    scope on the engine repo) is printed and swallowed, same as every other
    outbound notification in this module."""
    if paths.target_root() == paths.engine_root():
        return
    try:
        token = get_token()
        owner, repo = engine_repo_slug()
        fingerprint = _repair_fingerprint(story, result)
        existing = list_open_issues(owner, repo, token, label=SELF_HEAL_LABEL)
        if any(fingerprint in (issue.get("body") or "") for issue in existing):
            return
        title, body = _format_upstream_issue(story, result, fingerprint)
        create_issue(owner, repo, token, title, body, labels=[SELF_HEAL_LABEL])
    except GitHubError as exc:
        print(f"upstream system-repair filing skipped: {exc}")


def _observe_and_report(
    story: Story, invoke_fn, failure_reason: str, *, state_path: str | Path | None = None
) -> None:
    """Run the read-only observer on a non-done ticket and surface its verdict
    on the source issue (self-heal lens). Best-effort throughout: it never
    raises and never changes the ticket's outcome. The observer only diagnoses;
    it files/edits nothing — the human acts on the comment + label.

    `state_path` (and the `invoke_fn`'s cwd) target the tree the work happened
    in: the main repo for the sequential path, but a worker's worktree for a
    parallel ticket so the diagnosis sees that ticket's changes (#4). Defaults
    to the target repo's state.json.

    The whole-repo pass is the one place we deliberately spend big context, so
    it runs only on a non-done outcome (bounded by failure frequency), once, and
    can be switched off via budgets.observer_enabled.
    """
    number = source_issue_number(story.id)
    result = run_observer(
        story, invoke_fn, failure_reason,
        state_path=state_path if state_path is not None else paths.state_path(),
    )
    if result.problem is not None:
        print(f"observer skipped: {result.problem}")
        return
    if result.classification == "harness" and result.repair:
        _file_upstream_repair(story, result)
    if number is None:
        return  # plain S-NNN: nothing to post to; the run log holds the analysis
    if result.classification == "harness" and result.repair:
        _post_observer(number, _format_repair_comment(story, result), SELF_HEAL_LABEL)
    else:
        body = (
            f"🔎 `{story.id}` observer — **ticket-level**: {result.summary}\n\n"
            "This looks specific to the ticket, not the harness. Clarify or "
            "refine the issue, then re-run."
        )
        _post_observer(number, body, CLARIFY_LABEL)


_PROGRESS_EMOJI = {"success": "✅", "failure": "⚠️", "blocked": "⛔", "halted": "⛔"}


def _make_progress_fn(story: Story):
    """A per-stage progress poster for a GH-sourced ticket, else None (S-014).

    Returns a callable the orchestrator invokes on each stage transition; it
    comments the stage outcome on the source issue so the phone gets a running
    log. Best-effort: any GitHub/credential failure is printed and swallowed,
    so a notification problem can never change the ticket's outcome. Stories
    with no source issue (plain S-NNN) get None — nothing is posted."""
    issue_number = source_issue_number(story.id)
    if issue_number is None:
        return None

    def post(stage: str, outcome: str, summary: str = "") -> None:
        marker = _PROGRESS_EMOJI.get(outcome, "▶")
        body = f"{marker} `{story.id}` — **{stage}**: {outcome}"
        # Append the stage's own one-line summary so the phone sees what each
        # stage actually did (its plan, the tests it ran, the review verdict),
        # not just a bare outcome word.
        if summary and summary.strip():
            body += f"\n\n{summary.strip()}"
        try:
            token = get_token()
            owner, repo = repo_slug()
            comment_on_issue(owner, repo, token, issue_number, body)
        except GitHubError as exc:
            print(f"progress comment skipped: {exc}")

    return post


def _make_stage_label_fn(story: Story):
    """A per-stage board-label setter for a GH-sourced ticket, else None (S-016).

    Returns a callable the orchestrator invokes once at each stage's entry; it
    swaps the issue's `stage:<x>` label for the new one so a GitHub Projects
    board can show the stage currently in flight. Mutually exclusive: the prior
    stage label is removed when the next is added. Best-effort throughout —
    reuses `_set_run_label`'s GitHub-error swallowing, so a notification
    problem can never change the ticket's outcome. Stories with no source
    issue (plain S-NNN) get None — nothing is called."""
    issue_number = source_issue_number(story.id)
    if issue_number is None:
        return None

    prev: str | None = None

    def set_stage(stage: str) -> None:
        nonlocal prev
        label = STAGE_LABEL_PREFIX + stage
        remove = (prev,) if prev and prev != label else ()
        _set_run_label(story, remove=remove, add=(label,))
        prev = label

    return set_stage


def _read_asset(path: Path) -> str | None:
    """Read an engine prompt asset, or None if it is absent/unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _stage_spec_name(stage: str) -> str | None:
    """The stage spec filename for `stage`: `<stage>_feat.md` (plan/implement/
    test/review/decompose/document) or `<stage>.md` (observe), whichever exists
    in the resolved stage_specs dir."""
    specs = paths.stage_specs_dir()
    for name in (f"{stage}_feat.md", f"{stage}.md"):
        if (specs / name).exists():
            return name
    return None


def _plan_manifest(run_dir: Path) -> str | None:
    """Render the latest plan output's `file_manifest` (if any) as a markdown
    section telling downstream stages exactly which files to open, instead of
    re-surveying the repo (GH-61). Degrades to None on any missing/unparseable
    plan output or absent/empty manifest — a bad manifest costs a little
    re-exploration, never a stuck stage."""
    plan_outputs = sorted(run_dir.glob("iter*_plan_output.md"))
    if not plan_outputs:
        return None
    try:
        block = parse_status_block(plan_outputs[-1].read_text(encoding="utf-8"))
    except (StatusBlockError, OSError):
        return None
    manifest = block.file_manifest
    if not manifest:
        return None
    edit = manifest.get("edit") or []
    read = manifest.get("read") or []
    if not edit and not read:
        return None
    lines = [
        "## File manifest (from the plan)\n",
        "Open only these, do not survey the codebase; if the manifest is "
        "wrong or insufficient, read more and say so.\n",
    ]
    if edit:
        lines.append("Edit:\n" + "\n".join(f"- {p}" for p in edit) + "\n")
    if read:
        lines.append("Read:\n" + "\n".join(f"- {p}" for p in read) + "\n")
    return "\n".join(lines)


def compose_stage_prompt(stage: str, state: State, story: Story, run_dir: Path) -> Path:
    """Concatenate the stage's command file, the inlined orientation + stage
    spec, and the ticket/state context.

    The orientation (commands/PRIME.md) and the stage spec (stage_specs/<x>) are
    INLINED rather than left as "Read this file" instructions: when the harness
    builds another repo (ADW_REPO), the stage agent's cwd is the *target*, where
    those engine files don't exist, so a relative Read would 404. Inlining them
    here — resolved from the engine via adw/paths.py — makes the prompt
    self-contained regardless of which repo is being built. Self-hosting the
    content is identical to what the agent used to Read for itself."""
    command_file = paths.commands_dir() / f"{stage.upper()}.md"
    if not command_file.exists():
        raise FileNotFoundError(
            f"{command_file} missing — stage entry commands are owned by "
            "plans/prompts_plan.md and must exist before workflows can run."
        )
    sections = [command_file.read_text(encoding="utf-8")]

    # Inline orientation + spec so a target-cwd agent gets them without a disk read.
    prime = _read_asset(paths.commands_dir() / "PRIME.md")
    spec_name = _stage_spec_name(stage)
    spec_text = _read_asset(paths.stage_specs_dir() / spec_name) if spec_name else None
    if prime or spec_text:
        sections.append(
            "---\n\n_The orientation and stage spec your command refers to are "
            "inlined below in full — follow them from here; do **not** try to "
            "`Read` them from disk (when this harness builds another repo they "
            "are not in your working directory)._"
        )
    if prime:
        sections.append("## Orientation — `commands/PRIME.md` (inlined)\n\n" + prime)
    if spec_text:
        sections.append(f"## Stage spec — `stage_specs/{spec_name}` (inlined)\n\n" + spec_text)

    ticket_context = json.dumps(
        {
            "ticket": {
                "id": story.id,
                "type": story.type,
                "title": story.title,
                "description": story.description,
                "acceptance_criteria": story.acceptance_criteria,
                "skill_match": story.skill_match,
            },
            "state": {
                "stage": stage,
                "iteration": state.iteration,
                "branch": state.branch,
                "last_failure": state.last_failure,
            },
        },
        indent=2,
    )
    sections.append("## Your ticket and state\n\n```json\n" + ticket_context + "\n```\n")
    prompt = "\n\n".join(sections)
    # Prior stage outputs are the hand-off within a run (plans/harness_plan.md
    # §5): the plan stage is read-only, so its plan reaches implement/test/
    # review as a saved output file the agent can Read.
    prior_outputs = sorted(run_dir.glob("iter*_output.md"))
    if prior_outputs:
        listing = "\n".join(f"- {p.as_posix()}" for p in prior_outputs)
        prompt += (
            "\n## Prior stage outputs this run\n\n"
            "Read the ones relevant to your stage (the latest plan output "
            "is your work order):\n" + listing + "\n"
        )
    manifest_section = _plan_manifest(run_dir) if stage in ("implement", "test", "review") else None
    if manifest_section:
        prompt += "\n" + manifest_section + "\n"
    prompt_path = run_dir / f"iter{state.iteration:02d}_{stage}_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


# --- Work / coordination split (#4) -----------------------------------------
#
# run_one_story is factored into a per-ticket WORK half and a COORDINATION
# half so the sequential path and each parallel worker share one work
# implementation (plans/parallelization_plan.md):
#
#   WORK (worktree-scoped, NO shared-state writes): run_ticket_work — drives
#     the story through its stages in a given `cwd`/`state_path`. A parallel
#     worker runs this in its own worktree and returns a TicketOutcome.
#
#   COORDINATION (parent-only, owns prd.json/GitHub): _mark_in_progress,
#     _decompose_and_persist, _finalize_story, _finalize_decompose_block.
#     ONLY these write prd.json, push branches, relabel, or run the observer,
#     so workers never touch shared state and post-processing stays serial.
#
# The sequential run_one_story composes them back-to-back; the parallel
# coordinator (run_backlog_parallel) calls the same pieces across threads.


def _make_invoke(story: Story, run_dir: Path, *, models: dict, budgets: dict, cwd: str | Path):
    """Build the stage-invocation closure, bound to `cwd` (the tree the agent
    operates on) and `run_dir` (where its prompt/output land). The sequential
    path passes the target repo; a parallel worker passes its worktree (#4)."""
    timeout_seconds = budgets["stage_timeout_minutes"] * 60

    def invoke(stage: str, state: State, story: Story):
        prompt_path = compose_stage_prompt(stage, state, story, run_dir)
        result = invoke_stage(
            prompt_path,
            stage=stage,
            model=models[stage],
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        output_path = run_dir / f"iter{state.iteration:02d}_{stage}_output.md"
        output_text = result.raw_output
        if result.stderr.strip():
            output_text += f"\n\n## stage stderr\n\n```\n{result.stderr.strip()}\n```\n"
        output_path.write_text(output_text, encoding="utf-8")
        return result

    return invoke


def _mark_in_progress(story: Story) -> None:
    """Coordination: flip the story to in_progress in prd.json, commit, and flag
    the source issue as running (best-effort; no-op for plain S-NNN)."""
    prd = load_prd(paths.prd_path())
    mark_story(prd, story.id, status="in_progress")
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: mark {story.id} in_progress")
    _set_run_label(story, add=(RUN_LABEL_IN_PROGRESS,))


def _decompose_and_persist(story: Story, invoke_fn, progress, *, state_path: str | Path) -> str | None:
    """Coordination: expand a criteria-less ticket and persist the proposed
    acceptance criteria to prd.json (the orchestrator persists, never the
    agent — S-013). Returns a problem string to block on, or None when criteria
    were persisted and `story.acceptance_criteria` was updated in place.

    Always runs in the parent (read-only, against the target repo) so workers
    only ever see fully-specified stories (#4)."""
    criteria, problem = run_decompose(story, invoke_fn, state_path=state_path)
    if progress is not None:
        if problem is not None:
            progress("decompose", "blocked", problem)
        else:
            progress("decompose", "success", f"{len(criteria)} acceptance criteria proposed")
    if problem is not None:
        return problem
    story.acceptance_criteria = criteria
    prd = load_prd(paths.prd_path())
    get_story(prd, story.id).acceptance_criteria = criteria
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: decompose {story.id} into acceptance criteria")
    return None


def run_ticket_work(
    story: Story,
    stage_order: tuple[str, ...],
    *,
    models: dict,
    budgets: dict,
    max_iterations: int,
    cwd: str | Path,
    state_path: str | Path,
    run_dir: Path,
    progress_fn=None,
    stage_fn=None,
) -> TicketOutcome:
    """The per-ticket WORK: drive `story` through `stage_order` inside `cwd`,
    writing stage state to `state_path` and logs to `run_dir`. Performs NO
    shared-state writes (no prd.json, no GitHub) — the parent coordinator owns
    those. Shared by the sequential path (cwd = target repo) and each parallel
    worker (cwd = its worktree, with a worktree-local state.json)."""
    invoke = _make_invoke(story, run_dir, models=models, budgets=budgets, cwd=cwd)
    return run_ticket(
        story,
        invoke,
        stage_order=stage_order,
        state_path=state_path,
        max_iterations=max_iterations,
        breaker=CircuitBreaker(SafetyConfig.from_budgets(paths.budgets_path())),
        verify_fn=_make_verify_fn(budgets, cwd=cwd),
        progress_fn=progress_fn,
        stage_fn=stage_fn,
    )


def _finalize_story(
    story: Story,
    outcome: TicketOutcome,
    *,
    observer_invoke,
    observer_state_path: str | Path,
    budgets: dict,
) -> None:
    """Coordination: record a finished ticket's outcome in prd.json, swap its
    issue label, notify GitHub (push + PR + comment), and, on a non-done
    outcome, run the whole-repo observer (self-heal lens). Parent-only and
    serialized, so prd writes never race and the observer's agent cost is never
    multiplied across N tickets (#4).

    `observer_invoke`/`observer_state_path` target the tree the work happened
    in — the worktree for a parallel ticket, the target repo for sequential."""
    if outcome.outcome == "quotad":
        # A quota cut-off interrupted otherwise-good work: no PR (work is
        # incomplete) and no observer (spending a big agent call right when
        # we just ran out of usage is the opposite of helpful, S-015). The
        # story stays auto-resumable (adw/tickets.py pick_next_story) once
        # its cooldown elapses, unlike 'blocked' which is human-gated.
        prd = load_prd(paths.prd_path())
        mark_story(prd, story.id, status="quotad")
        save_prd(prd, paths.prd_path())
        _commit_bookkeeping(f"chore: record {story.id} outcome: quotad")
        _set_run_label(story, remove=(RUN_LABEL_IN_PROGRESS,), add=(RUN_LABEL_QUOTAD,))
        return
    prd = load_prd(paths.prd_path())
    if outcome.outcome == "done":
        mark_story(prd, story.id, status="done", passes=True)
    else:
        mark_story(prd, story.id, status="blocked")
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: record {story.id} outcome: {outcome.outcome}")
    # Swap the in-progress label for the terminal one; the issue stays OPEN
    # (label-only) so it closes on PR merge, the human gate.
    if outcome.outcome == "done":
        _set_run_label(story, remove=(RUN_LABEL_IN_PROGRESS,), add=(RUN_LABEL_DONE,))
    else:
        _set_run_label(story, remove=(RUN_LABEL_IN_PROGRESS,), add=(RUN_LABEL_BLOCKED,))
    _notify_github(
        story, outcome.outcome, outcome.reason or "", outcome.test_evidence,
        outcome.pr_description,
    )
    if outcome.outcome != "done" and budgets.get("observer_enabled", True):
        _observe_and_report(
            story, observer_invoke, outcome.reason or "", state_path=observer_state_path
        )


def _finalize_decompose_block(
    story: Story,
    problem: str,
    *,
    observer_invoke,
    observer_state_path: str | Path,
    budgets: dict,
) -> TicketOutcome:
    """Coordination: a ticket that could not be expanded into acceptance
    criteria blocks here, before any worktree/work. Mark it blocked, relabel,
    and run the observer. No GitHub PR notify — nothing was implemented, so
    there is no work branch to open (matches the original sequential path)."""
    prd = load_prd(paths.prd_path())
    mark_story(prd, story.id, status="blocked")
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: record {story.id} outcome: blocked")
    _set_run_label(story, remove=(RUN_LABEL_IN_PROGRESS,), add=(RUN_LABEL_BLOCKED,))
    if budgets.get("observer_enabled", True):
        _observe_and_report(
            story, observer_invoke, problem, state_path=observer_state_path
        )
    return TicketOutcome(story.id, "blocked", reason=problem, stages_run=["decompose"])


def run_one_story(
    story: Story,
    stage_order: tuple[str, ...],
    *,
    models: dict,
    budgets: dict,
    max_iterations: int,
) -> TicketOutcome:
    """Run one story through `stage_order` and record its outcome in prd.json.
    Shared by the single-ticket CLI (run_workflow) and the sequential backlog
    runner. Composes the work + coordination halves back-to-back against the
    target repo; the parallel coordinator wires the same halves across worktrees.
    """
    _ensure_work_branch(f"adw/{story.id}")
    _mark_in_progress(story)
    run_dir = runlog.run_dir(story.id)
    target = paths.target_root()
    state_path = paths.state_path()
    invoke = _make_invoke(story, run_dir, models=models, budgets=budgets, cwd=target)
    # Progress poster: comments stage transitions on the source issue so a
    # phone-filed ticket reports back live (S-014). None for plain S-NNN.
    progress = _make_progress_fn(story)
    # Stage-label poster: swaps a `stage:<x>` board label on the source issue
    # at each stage's entry (S-016). None for plain S-NNN.
    stage_label = _make_stage_label_fn(story)

    # Decompose first if the ticket arrived criteria-less (e.g. a terse phone
    # issue, S-013): the read-only decompose stage proposes acceptance criteria
    # and the orchestrator (here, not the agent) persists them to prd.json
    # before planning. A vague ticket that cannot be expanded blocks here.
    if not story.acceptance_criteria:
        problem = _decompose_and_persist(story, invoke, progress, state_path=state_path)
        if problem is not None:
            return _finalize_decompose_block(
                story, problem,
                observer_invoke=invoke, observer_state_path=state_path, budgets=budgets,
            )

    outcome = run_ticket_work(
        story, stage_order,
        models=models, budgets=budgets, max_iterations=max_iterations,
        cwd=target, state_path=state_path, run_dir=run_dir, progress_fn=progress,
        stage_fn=stage_label,
    )
    _finalize_story(
        story, outcome,
        observer_invoke=invoke, observer_state_path=state_path, budgets=budgets,
    )
    return outcome


def run_workflow(
    stage_order: tuple[str, ...],
    *,
    ticket_types: tuple[str, ...] | None = None,
    description: str = "",
) -> int:
    """Drive one ticket through `stage_order`. Returns a process exit code
    (0 = done, 1 = blocked/halted/cooldown-refused).

    `ticket_types` filters auto-selection so each workflow only picks the
    ticket types it is built for; an explicit --ticket overrides the filter.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--ticket", help="story id; defaults to highest-priority open story")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument(
        "--override-cooldown",
        action="store_true",
        help="start despite an active circuit cooldown (human judgment call)",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help="run stage sessions inside a docker container (plans/safety_plan.md §5); "
        "equivalent to setting ADW_ISOLATION=1. Requires a running Docker daemon "
        "and the adw-sandbox image — see README 'Container isolation'.",
    )
    args = parser.parse_args()
    if args.isolate:
        os.environ[isolation.ISOLATION_ENV] = "1"

    cooldown_msg = check_cooldown(paths.state_path())
    if cooldown_msg and not args.override_cooldown:
        print(f"refusing to start: {cooldown_msg}")
        print("pass --override-cooldown to start anyway")
        return 1

    models = json.loads(paths.models_path().read_text(encoding="utf-8"))
    budgets = json.loads(paths.budgets_path().read_text(encoding="utf-8"))
    max_iterations = args.max_iterations or budgets["max_iterations_default"]

    prd = load_prd(paths.prd_path())
    story = (
        get_story(prd, args.ticket)
        if args.ticket
        else pick_next_story(prd, types=ticket_types)
    )
    if story is None:
        print("no open story with passes=false — nothing to do")
        return 0

    outcome = run_one_story(
        story, stage_order, models=models, budgets=budgets, max_iterations=max_iterations
    )
    if outcome.outcome == "done":
        # Merge to main stays a human gate (plans/safety_plan.md §4); the
        # ticket is done, the branch awaits review/merge.
        print(f"{story.id} done after {outcome.iterations} iteration(s); "
              f"branch adw/{story.id} ready for merge gate")
    else:
        print(f"{story.id} {outcome.outcome}: {outcome.reason}")
    return 0 if outcome.outcome == "done" else 1


@dataclass
class BacklogResult:
    tickets_run: int
    stop_reason: str
    clean: bool  # True if the loop ended on an empty backlog or the bound


def run_backlog_loop(
    *,
    run_story_fn,
    cooldown_fn,
    max_tickets: int,
    prd_path=None,
    state_path=None,
) -> BacklogResult:
    """Outer loop over open stories (snarktank/ralph pattern). Picks the next
    open story, runs it via run_story_fn, and repeats until the backlog empties
    or max_tickets is hit. Stops (never skips) on the first non-done outcome,
    and never overrides an active circuit cooldown. Adds no new authority — the
    inner safety model (run_ticket + breaker) is untouched. run_story_fn and
    cooldown_fn are injected so the loop is testable without real workflows."""
    prd_path = paths.prd_path() if prd_path is None else prd_path
    state_path = paths.state_path() if state_path is None else state_path
    count = 0
    while count < max_tickets:
        cooldown = cooldown_fn(state_path)
        if cooldown is not None:
            return BacklogResult(count, f"circuit cooldown active; stopping: {cooldown}", False)
        prd = load_prd(prd_path)
        story = pick_next_story(prd)
        if story is None:
            return BacklogResult(count, "no open stories remain", True)
        outcome = run_story_fn(story)
        count += 1
        if outcome.outcome != "done":
            return BacklogResult(
                count, f"stopped at {story.id}: {outcome.outcome} ({outcome.reason})", False
            )
    return BacklogResult(count, f"reached --max-tickets ({max_tickets})", True)


# --- Parallel backlog coordinator (#4, Tier 1) ------------------------------


def _safe_work(work_fn, story: Story, worktree_dir) -> TicketOutcome:
    """Run one worker, turning ANY exception into a blocked outcome so a single
    crashing worker never aborts the batch (failure isolation, #4)."""
    try:
        return work_fn(story, worktree_dir)
    except Exception as exc:  # noqa: BLE001 — deliberately catch-all; the batch must survive
        return TicketOutcome(
            story.id, "blocked", reason=f"worker raised {exc.__class__.__name__}: {exc}"
        )


def run_backlog_parallel(
    *,
    prepare_fn,
    work_fn,
    finalize_fn,
    block_fn,
    cooldown_fn,
    add_worktree_fn,
    remove_worktree_fn,
    max_tickets: int,
    max_parallel: int,
    prd_path=None,
    state_path=None,
) -> BacklogResult:
    """Run the open backlog in parallel batches of up to `max_parallel` tickets,
    each isolated in its own git worktree (plans/parallelization_plan.md). The
    parent owns all shared state; workers only run the per-ticket work.

    Per batch: check cooldown ONCE (workers never override it), pick the top N
    open stories by (priority, id), `prepare` each serially (decompose + persist
    + mark in_progress — a ticket that cannot be expanded blocks here via
    `block_fn` and never reaches a worktree), add a worktree per survivor, run
    the survivors' work concurrently in threads, then reconcile their outcomes
    SERIALLY via `finalize_fn` (prd writes, notify, observer). Worktrees are
    always removed in a `finally`. Unlike the sequential loop, a blocked ticket
    halts only its own worktree — the batch and backlog continue.

    The leaf operations are injected so the coordinator is testable without real
    git, agents, or GitHub:
      prepare_fn(story) -> str | None     (None = ready; str = blocked problem)
      work_fn(story, worktree_dir) -> TicketOutcome   [runs in a worker thread]
      finalize_fn(story, outcome, worktree_dir) -> None
      block_fn(story, problem) -> TicketOutcome
      add_worktree_fn(story) -> worktree_dir ; remove_worktree_fn(story) -> None
    """
    prd_path = paths.prd_path() if prd_path is None else prd_path
    state_path = paths.state_path() if state_path is None else state_path
    total = 0
    while total < max_tickets:
        cooldown = cooldown_fn(state_path)
        if cooldown is not None:
            return BacklogResult(total, f"circuit cooldown active; stopping: {cooldown}", False)
        prd = load_prd(prd_path)
        batch = pick_next_stories(prd, min(max_parallel, max_tickets - total))
        if not batch:
            return BacklogResult(total, "no open stories remain", True)
        total += len(batch)

        # Parent serial: prepare (decompose + persist + mark in_progress).
        # A ticket that cannot be expanded is finalized blocked now and never
        # gets a worktree; the rest survive to run.
        survivors: list[Story] = []
        for story in batch:
            problem = prepare_fn(story)
            if problem is not None:
                block_fn(story, problem)
            else:
                survivors.append(story)
        if not survivors:
            continue

        worktree_dirs: dict[str, object] = {}
        try:
            for story in survivors:
                worktree_dirs[story.id] = add_worktree_fn(story)
            # Concurrent work — threads, because the work is subprocess-bound
            # (invoke_stage) so real parallelism needs no process overhead.
            outcomes: dict[str, TicketOutcome] = {}
            with ThreadPoolExecutor(max_workers=len(survivors)) as pool:
                futures = {
                    pool.submit(_safe_work, work_fn, story, worktree_dirs[story.id]): story
                    for story in survivors
                }
                for fut in as_completed(futures):
                    story = futures[fut]
                    outcomes[story.id] = fut.result()
            # Reconcile SERIALLY (deterministic order) — prd writes, notify, and
            # the observer touch shared state or spend agent cost.
            for story in survivors:
                finalize_fn(story, outcomes[story.id], worktree_dirs[story.id])
        finally:
            for story in survivors:
                remove_worktree_fn(story)

    return BacklogResult(total, f"reached --max-tickets ({max_tickets})", True)


def run_parallel_backlog(
    *,
    max_tickets: int,
    max_iterations: int,
    max_parallel: int,
    models: dict,
    budgets: dict,
) -> BacklogResult:
    """Wire the work/coordination helpers to the generic parallel coordinator
    and run a bounded parallel backlog pass. The thin entry script
    (workflows/run_backlog.py --parallel) supplies configs."""

    def prepare(story: Story) -> str | None:
        # Decompose runs in the parent (read-only, against the target repo) so
        # workers only ever see fully-specified stories; then mark in_progress.
        if not story.acceptance_criteria:
            run_dir = runlog.run_dir(story.id)
            invoke = _make_invoke(
                story, run_dir, models=models, budgets=budgets, cwd=paths.target_root()
            )
            problem = _decompose_and_persist(
                story, invoke, _make_progress_fn(story), state_path=paths.state_path()
            )
            if problem is not None:
                return problem
        _mark_in_progress(story)
        return None

    def work(story: Story, worktree_dir) -> TicketOutcome:
        stage_order = STAGE_ORDER_BY_TYPE.get(story.type)
        if stage_order is None:  # defensive: schema restricts type, but never dispatch blind
            return TicketOutcome(story.id, "blocked", reason=f"no workflow for type {story.type!r}")
        worktree_dir = Path(worktree_dir)
        return run_ticket_work(
            story, stage_order,
            models=models, budgets=budgets, max_iterations=max_iterations,
            cwd=worktree_dir,
            state_path=worktree_dir / "state.json",
            run_dir=runlog.run_dir(story.id),
            progress_fn=_make_progress_fn(story),
            stage_fn=_make_stage_label_fn(story),
        )

    def finalize(story: Story, outcome: TicketOutcome, worktree_dir) -> None:
        # The observer (if it runs) sees the worktree — that is where this
        # ticket's changes live; the worktree is removed only after finalize.
        worktree_dir = Path(worktree_dir)
        observer_invoke = _make_invoke(
            story, runlog.run_dir(story.id), models=models, budgets=budgets, cwd=worktree_dir
        )
        _finalize_story(
            story, outcome,
            observer_invoke=observer_invoke,
            observer_state_path=worktree_dir / "state.json",
            budgets=budgets,
        )

    def block(story: Story, problem: str) -> TicketOutcome:
        # Decompose-blocked: no worktree exists, so the observer runs against
        # the target repo.
        invoke = _make_invoke(
            story, runlog.run_dir(story.id), models=models, budgets=budgets, cwd=paths.target_root()
        )
        return _finalize_decompose_block(
            story, problem,
            observer_invoke=invoke, observer_state_path=paths.state_path(), budgets=budgets,
        )

    return run_backlog_parallel(
        prepare_fn=prepare,
        work_fn=work,
        finalize_fn=finalize,
        block_fn=block,
        cooldown_fn=check_cooldown,
        add_worktree_fn=lambda story: worktrees.add_worktree(story.id),
        remove_worktree_fn=lambda story: worktrees.remove_worktree(story.id),
        max_tickets=max_tickets,
        max_parallel=max_parallel,
    )

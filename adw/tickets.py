"""prd.json ticket store: schema validation, story picking, status updates.

The schema is owned by plans/tickets_plan.md; this module enforces it.
The workflow (not the agent) calls these functions; agents only ever see
the picked story's content in their prompt.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

STORY_TYPES = ("feat", "bug", "chore", "system-repair")
STORY_STATUSES = ("open", "in_progress", "blocked", "quotad", "done")


class PrdValidationError(ValueError):
    """prd.json failed schema validation; the message lists every problem found."""


@dataclass
class Story:
    id: str
    type: str
    priority: int
    title: str
    description: str
    acceptance_criteria: list[str]
    skill_match: str | None = None
    passes: bool = False
    status: str = "open"


@dataclass
class Prd:
    project: str
    stories: list[Story] = field(default_factory=list)


def _validate_story(raw: dict, index: int, errors: list[str]) -> None:
    where = f"stories[{index}]"
    for key in ("id", "type", "priority", "title", "description", "acceptance_criteria"):
        if key not in raw:
            errors.append(f"{where}: missing required field '{key}'")
    if raw.get("type") not in STORY_TYPES:
        errors.append(f"{where}: type must be one of {STORY_TYPES}, got {raw.get('type')!r}")
    if raw.get("status", "open") not in STORY_STATUSES:
        errors.append(f"{where}: status must be one of {STORY_STATUSES}, got {raw.get('status')!r}")
    if not isinstance(raw.get("priority"), int):
        errors.append(f"{where}: priority must be an integer")
    criteria = raw.get("acceptance_criteria")
    # May be empty: a terse intake (e.g. a phone-filed GitHub issue) is stored
    # criteria-less and the decompose stage (S-013) fills it in before plan.
    # If present, every entry must still be a non-empty string.
    if not isinstance(criteria, list) or not all(
        isinstance(c, str) and c.strip() for c in criteria
    ):
        errors.append(f"{where}: acceptance_criteria must be a list of non-empty strings")
    if not isinstance(raw.get("passes", False), bool):
        errors.append(f"{where}: passes must be a boolean")


def _shard_dir(path: str | Path) -> Path:
    """The sharded ticket store anchored at `path` (the canonical prd.json
    location): one file per story under the sibling `prd/` directory."""
    return Path(path).parent / "prd"


def _build_prd(project, raw_stories: list, where: str, *, extra_errors=()) -> Prd:
    """Validate raw story dicts + a project label into a `Prd`, or raise.

    Shared by the sharded and legacy-single-file readers so both enforce the
    same schema and the same error format.
    """
    errors: list[str] = list(extra_errors)
    if not isinstance(project, str) or not project:
        errors.append("project: must be a non-empty string")
    for i, story in enumerate(raw_stories):
        _validate_story(story, i, errors)
    ids = [s.get("id") for s in raw_stories]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        errors.append(f"stories: duplicate ids {sorted(duplicates)}")
    if errors:
        raise PrdValidationError(f"{where}:\n" + "\n".join(errors))
    return Prd(
        project=project,
        stories=[
            Story(
                id=s["id"],
                type=s["type"],
                priority=s["priority"],
                title=s["title"],
                description=s["description"],
                acceptance_criteria=list(s["acceptance_criteria"]),
                skill_match=s.get("skill_match"),
                passes=s.get("passes", False),
                status=s.get("status", "open"),
            )
            for s in raw_stories
        ],
    )


def _load_sharded(shard_dir: Path) -> Prd:
    """Read `prd/_meta.json` (project) + every `prd/<id>.json` story shard.

    Stories are returned sorted by id — order is not stored on disk, so an
    unchanged story always reloads identically and the pickers (which re-sort
    by (priority, id)) never depend on it.
    """
    meta = json.loads((shard_dir / "_meta.json").read_text(encoding="utf-8"))
    extra: list[str] = []
    raw_stories: list[dict] = []
    for shard in shard_dir.glob("*.json"):
        if shard.name == "_meta.json":
            continue
        story = json.loads(shard.read_text(encoding="utf-8"))
        # The id lives in the file (source of truth); the filename is just its
        # location. Assert they agree as a cheap integrity check on hand-edits.
        if story.get("id") != shard.stem:
            extra.append(f"{shard.name}: id {story.get('id')!r} does not match filename")
        raw_stories.append(story)
    raw_stories.sort(key=lambda s: str(s.get("id")))
    return _build_prd(meta.get("project"), raw_stories, str(shard_dir), extra_errors=extra)


def _load_legacy(path: Path) -> Prd:
    """Read a pre-sharding single-file `prd.json` (read-only fallback)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw_stories = raw.get("stories")
    if not isinstance(raw_stories, list):
        return _build_prd(raw.get("project"), [], str(path), extra_errors=["stories: must be a list"])
    return _build_prd(raw.get("project"), raw_stories, str(path))


def load_prd(path: str | Path) -> Prd:
    """Load the ticket store anchored at `path` (the canonical prd.json location).

    Storage is sharded (GH-79): one file per story under the sibling `prd/`
    directory, plus `prd/_meta.json` for the project label. Two ticket branches
    that edit different stories touch different files, so their PRs merge to
    main without a prd conflict. If the shard directory is absent we fall back
    to reading a legacy single-file `prd.json` (read-only), so unmigrated
    branches and target repos still load until they drain.
    """
    path = Path(path)
    shard_dir = _shard_dir(path)
    if (shard_dir / "_meta.json").exists():
        return _load_sharded(shard_dir)
    if path.exists():
        return _load_legacy(path)
    raise FileNotFoundError(path)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` so a concurrent reader sees either the old file or
    the new one in full, never a half-written one (plans/safety_plan.md).

    A scheduled poll and a manual sync can race on prd.json with no lock: the
    naive truncate-then-write left a window where the loser of that race read a
    truncated/empty file and crashed `load_prd`. Writing to a temp file in the
    SAME directory (so the rename is same-filesystem and atomic), flushing +
    fsyncing it, then `os.replace`-ing over the target closes that window. On
    any failure the temp file is cleaned up and the original is left intact.
    """
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_prd(prd: Prd, path: str | Path) -> None:
    """Persist the store as shards under the sibling `prd/` directory (GH-79).

    Each story serializes to `prd/<id>.json` deterministically (stable dataclass
    field order, `ensure_ascii=True`) so an unchanged story writes byte-identical
    content — no git diff, no commit churn, nothing to conflict on. The project
    label goes to `prd/_meta.json`. Stories that disappeared from the store have
    their shards removed. A legacy single-file `prd.json` at `path` is left
    untouched (read-only tombstone) until stale branches drain.
    """
    shard_dir = _shard_dir(path)
    shard_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        shard_dir / "_meta.json",
        json.dumps({"project": prd.project}, indent=2) + "\n",
    )
    keep = set()
    for story in prd.stories:
        keep.add(story.id)
        _atomic_write_text(
            shard_dir / f"{story.id}.json",
            json.dumps(asdict(story), indent=2) + "\n",
        )
    for shard in shard_dir.glob("*.json"):
        if shard.name != "_meta.json" and shard.stem not in keep:
            shard.unlink()


def pick_next_story(prd: Prd, *, types: tuple[str, ...] | None = None) -> Story | None:
    """Highest-priority story with passes=false and status=open.

    If `types` is given, only stories of those types are considered, so each
    workflow auto-picks only the ticket types it is built for (feat vs bug
    vs chore). system-repair stories are filed as 'blocked' (human-gated,
    see plans/tickets_plan.md §5), so they are never picked until a human
    flips them to 'open'. A 'quotad' story (halted only by a provider usage
    limit, S-015) is picked alongside 'open' so it auto-resumes once its
    cooldown elapses; 'blocked' stays human-gated and excluded.
    """
    candidates = [
        s
        for s in prd.stories
        if not s.passes
        and s.status in ("open", "quotad")
        and (types is None or s.type in types)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda s: (s.priority, s.id))


def pick_next_stories(prd: Prd, n: int, *, types: tuple[str, ...] | None = None) -> list[Story]:
    """The top `n` open stories by (priority, id) — the parallel batch (#4).

    `pick_next_story` is the n=1 case; this returns up to `n` of the same
    candidates (passes=false, status in open/quotad) in the same deterministic
    order, so the parallel coordinator can run several independent tickets at
    once. system-repair stories stay excluded (filed as 'blocked', human-gated).
    A 'quotad' story is eligible alongside 'open' so it auto-resumes once its
    cooldown elapses; 'blocked' stays human-gated and excluded."""
    candidates = [
        s
        for s in prd.stories
        if not s.passes
        and s.status in ("open", "quotad")
        and (types is None or s.type in types)
    ]
    candidates.sort(key=lambda s: (s.priority, s.id))
    return candidates[: max(0, n)]


def reclaim_stale_in_progress(
    prd: Prd,
    *,
    stale_seconds: float,
    live_ticket_id: str | None,
    state_age_seconds: float | None,
) -> list[str]:
    """Flip every stranded `in_progress` story back to a pickable state unless
    it is provably the one a live run is working (GH-47): `state.json`'s
    `ticket_id` matches it AND its heartbeat (mtime age) is within
    `stale_seconds`. A missing heartbeat (`state_age_seconds` or
    `live_ticket_id` is None) is never treated as live. Pure — no IO; the
    caller supplies the heartbeat reading. Returns the ids reclaimed, in story
    order.

    A `system-repair` ticket is restored to `blocked`, not `open` (GH-78): it
    is human-gated (only a human flips it to `open`), so reclaiming a stale one
    to `open` would silently re-arm it for auto-pick — exactly the gate-bypass
    that re-ran already-merged GH-56/GH-61. Every other type returns to `open`.
    """
    reclaimed: list[str] = []
    for s in prd.stories:
        if s.status != "in_progress":
            continue
        live = (
            live_ticket_id == s.id
            and state_age_seconds is not None
            and state_age_seconds <= stale_seconds
        )
        if not live:
            s.status = "blocked" if s.type == "system-repair" else "open"
            reclaimed.append(s.id)
    return reclaimed


def reconcile_completed(prd: Prd, completed_ids: set[str]) -> list[str]:
    """Mark any story whose work is already merged to `origin/main` (its id is
    in `completed_ids`) as terminal — `passes=true`, `status='done'` — so a
    local `prd.json` that has drifted behind `origin/main` can never re-select
    an already-merged ticket (GH-78). This is the type-agnostic terminal-guard:
    GH-56 (a feat re-typed to system-repair) and GH-61 were both re-run after
    merging because the local ledger had been reset to a pickable state. Pure —
    no IO; the caller supplies the merged-id set. Returns the ids changed, in
    story order."""
    changed: list[str] = []
    for s in prd.stories:
        if s.id in completed_ids and not (s.passes and s.status == "done"):
            s.passes = True
            s.status = "done"
            changed.append(s.id)
    return changed


def get_story(prd: Prd, story_id: str) -> Story:
    for story in prd.stories:
        if story.id == story_id:
            return story
    raise KeyError(f"no story with id {story_id!r}")


def mark_story(
    prd: Prd,
    story_id: str,
    *,
    status: str | None = None,
    passes: bool | None = None,
) -> Story:
    story = get_story(prd, story_id)
    if status is not None:
        if status not in STORY_STATUSES:
            raise ValueError(f"status must be one of {STORY_STATUSES}, got {status!r}")
        story.status = status
    if passes is not None:
        story.passes = passes
    return story


def next_story_id(prd: Prd) -> str:
    """Next free S-NNN id."""
    numbers = [
        int(s.id.split("-", 1)[1])
        for s in prd.stories
        if s.id.startswith("S-") and s.id.split("-", 1)[1].isdigit()
    ]
    return f"S-{(max(numbers, default=0) + 1):03d}"


def file_system_repair_story(
    prd: Prd,
    *,
    title: str,
    description: str,
    evidence: list[str],
    priority: int = 1,
) -> Story:
    """File a human-gated harness-repair ticket.

    Created as status='blocked' so pick_next_story never auto-executes it;
    a human approves by setting status to 'open'. The evidence becomes the
    acceptance criteria so the eventual fix is checkable.
    """
    story = Story(
        id=next_story_id(prd),
        type="system-repair",
        priority=priority,
        title=title,
        description=description,
        acceptance_criteria=evidence,
        status="blocked",
    )
    prd.stories.append(story)
    return story

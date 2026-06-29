"""Sync open GitHub Issues labeled 'adw' into prd.json as stories.

Usage: uv run python workflows/sync_issues.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# REPO_ROOT here is the ENGINE root, used only to import the adw package; the
# repo we sync into is the *target* (adw/paths.py), which may differ.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw import paths
from adw.github import GitHubError, get_token, list_adw_issues, repo_slug
from adw.tickets import Prd, Story, load_prd, save_prd

_TYPE_LABELS = {"feat", "bug", "chore", "system-repair"}
ROUTINE_SKIP_REASON = "already synced"


def issue_story_id(issue: dict) -> str:
    return f"GH-{issue['number']}"


# Phone/paste often prefixes every line with a quote bar (Markdown '>', or the
# block glyphs ▎ ┃ a renderer inserts). Strip those so a quoted body still
# parses its heading and bullets (motivating case: issue #16).
_QUOTE_PREFIX = re.compile(r"^[ \t]*(?:[>▎┃|][ \t]?)+")


def _dequote(text: str) -> str:
    return "\n".join(_QUOTE_PREFIX.sub("", line) for line in text.splitlines())


def parse_issue_body(body: str) -> tuple[str, list[str]]:
    """Split issue body into (description, acceptance_criteria).

    Tolerates leading quote bars/indentation, then looks for a heading matching
    /^#+\\s*acceptance criteria/i. Description = everything before it; criteria =
    non-empty bullet lines after it. A body with no such heading yields empty
    criteria (the decompose stage fills them in later).
    """
    if not body:
        return "", []
    body = _dequote(body)
    # Accept a markdown heading (`## Acceptance criteria`) OR a bold line
    # (`**Acceptance criteria**`) — a phone paste or hand-filed issue often uses
    # the bold form, and an unparsed heading silently drops the criteria (then
    # decompose has to regenerate them, an extra agent call).
    parts = re.split(
        r"(?im)^\s*(?:#+|\*\*)\s*acceptance criteria\s*(?:\*\*)?\s*$", body, maxsplit=1
    )
    description = parts[0].strip()
    if len(parts) < 2:
        return description, []
    criteria_block = parts[1]
    criteria = []
    for line in criteria_block.splitlines():
        m = re.match(r"^\s*[-*]\s*(?:\[[ x]\]\s*)?(.+)", line)
        if m:
            text = m.group(1).strip()
            if text:
                criteria.append(text)
    return description, criteria


def skip_reason(issue: dict) -> str | None:
    """Return a reason string if the issue should be skipped, else None.

    Missing acceptance criteria is NOT a skip (S-013): a terse issue is
    accepted criteria-less and the decompose stage expands it. Only a wrong
    type label or a genuinely empty issue (no title and no body) is skipped.
    """
    labels = {lb["name"] for lb in issue.get("labels", [])}
    type_labels = labels & _TYPE_LABELS
    if len(type_labels) != 1:
        return f"expected exactly one type label ({_TYPE_LABELS}), got {sorted(type_labels)}"
    if not (issue.get("title") or "").strip() and not (issue.get("body") or "").strip():
        return "issue has no title or body to build a story from"
    return None


def issue_to_story(issue: dict) -> Story:
    """Convert a well-formed GitHub issue dict to a Story."""
    labels = {lb["name"] for lb in issue.get("labels", [])}
    type_label = next(lb for lb in labels if lb in _TYPE_LABELS)

    priority = 5
    for lb in labels:
        m = re.match(r"^(?:p|priority-)(\d+)$", lb, re.IGNORECASE)
        if m:
            priority = int(m.group(1))
            break

    description, criteria = parse_issue_body(issue.get("body") or "")
    sid = issue_story_id(issue)
    title = issue.get("title", "").strip()
    # The issue title carries the id prefix by convention ("GH-1: Title"); the id
    # is tracked separately, so strip it here to avoid a doubled "GH-1: GH-1: …"
    # in the PR title and outcome comments.
    if title.lower().startswith(f"{sid.lower()}:"):
        title = title[len(sid) + 1:].strip()
    return Story(
        id=sid,
        type=type_label,
        priority=priority,
        title=title,
        description=description,
        acceptance_criteria=criteria,
    )


def sync_issues(prd: Prd, issues: list[dict]) -> tuple[list[Story], list[tuple[str, str]]]:
    """Apply issues onto prd in-place. Returns (added_stories, skipped_pairs)."""
    existing_ids = {s.id for s in prd.stories}
    added: list[Story] = []
    skipped: list[tuple[str, str]] = []

    for issue in issues:
        sid = issue_story_id(issue)
        if sid in existing_ids:
            skipped.append((sid, "already synced"))
            continue
        reason = skip_reason(issue)
        if reason:
            skipped.append((sid, reason))
            continue
        story = issue_to_story(issue)
        prd.stories.append(story)
        existing_ids.add(sid)
        added.append(story)

    return added, skipped


def pull_and_sync() -> tuple[list[Story], list[tuple[str, str]]]:
    """Fetch open `adw` issues and merge them into the target prd.json.
    Returns (added, skipped). Raises GitHubError if GitHub is unreachable —
    the caller decides whether that is fatal (poll_once stops before the
    backlog so it never runs on a stale sync)."""
    token = get_token()
    owner, repo = repo_slug()
    issues = list_adw_issues(owner, repo, token)
    prd = load_prd(paths.prd_path())
    added, skipped = sync_issues(prd, issues)
    save_prd(prd, paths.prd_path())
    return added, skipped


def main() -> int:
    try:
        added, skipped = pull_and_sync()
    except GitHubError as exc:
        print(f"github error: {exc}", file=sys.stderr)
        return 1

    print(f"added {len(added)} story(ies), skipped {len(skipped)}")
    for sid, reason in skipped:
        print(f"  skipped {sid}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

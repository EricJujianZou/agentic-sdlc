"""Sync open GitHub Issues labeled 'adw' into prd.json as stories.

Usage: uv run python workflows/sync_issues.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw.github import GitHubError, get_token, list_adw_issues, repo_slug
from adw.tickets import Prd, Story, load_prd, save_prd

PRD_PATH = REPO_ROOT / "prd.json"

_TYPE_LABELS = {"feat", "bug", "chore", "system-repair"}


def issue_story_id(issue: dict) -> str:
    return f"GH-{issue['number']}"


def parse_issue_body(body: str) -> tuple[str, list[str]]:
    """Split issue body into (description, acceptance_criteria).

    Looks for a heading matching /^#+\\s*acceptance criteria/i.
    Description = everything before it; criteria = non-empty bullet lines after it.
    """
    if not body:
        return "", []
    parts = re.split(r"(?im)^#+\s*acceptance criteria\s*$", body, maxsplit=1)
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
    """Return a reason string if the issue should be skipped, else None."""
    labels = {lb["name"] for lb in issue.get("labels", [])}
    type_labels = labels & _TYPE_LABELS
    if len(type_labels) != 1:
        return f"expected exactly one type label ({_TYPE_LABELS}), got {sorted(type_labels)}"
    _, criteria = parse_issue_body(issue.get("body") or "")
    if not criteria:
        return "no acceptance criteria found in issue body"
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
    return Story(
        id=issue_story_id(issue),
        type=type_label,
        priority=priority,
        title=issue.get("title", "").strip(),
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


def main() -> int:
    try:
        token = get_token()
        owner, repo = repo_slug()
        issues = list_adw_issues(owner, repo, token)
    except GitHubError as exc:
        print(f"github error: {exc}", file=sys.stderr)
        return 1

    prd = load_prd(PRD_PATH)
    added, skipped = sync_issues(prd, issues)
    save_prd(prd, PRD_PATH)

    print(f"added {len(added)} story(ies), skipped {len(skipped)}")
    for sid, reason in skipped:
        print(f"  skipped {sid}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

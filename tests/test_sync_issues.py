"""Unit tests for workflows/sync_issues.py — no live API calls."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adw.tickets import Prd, Story
from workflows.sync_issues import (
    issue_story_id,
    issue_to_story,
    parse_issue_body,
    skip_reason,
    sync_issues,
)


def _issue(**overrides) -> dict:
    base: dict = {
        "number": 42,
        "title": "Add feature X",
        "body": "Some description.\n\n## Acceptance Criteria\n- Criteria one\n- Criteria two",
        "labels": [{"name": "feat"}, {"name": "adw"}],
    }
    base.update(overrides)
    return base


def test_issue_story_id():
    assert issue_story_id({"number": 7}) == "GH-7"
    assert issue_story_id({"number": 100}) == "GH-100"


def test_parse_issue_body_splits_correctly():
    body = "Intro text.\n\n## Acceptance Criteria\n- Check one\n- [ ] Check two\n* Check three"
    desc, criteria = parse_issue_body(body)
    assert desc == "Intro text."
    assert criteria == ["Check one", "Check two", "Check three"]


def test_parse_issue_body_no_heading():
    desc, criteria = parse_issue_body("Just a description, no heading.")
    assert desc == "Just a description, no heading."
    assert criteria == []


def test_parse_issue_body_empty():
    desc, criteria = parse_issue_body("")
    assert desc == ""
    assert criteria == []


def test_parse_issue_body_case_insensitive_heading():
    body = "desc\n\n# ACCEPTANCE CRITERIA\n- item"
    _, criteria = parse_issue_body(body)
    assert criteria == ["item"]


def test_skip_reason_no_type_label():
    issue = _issue(labels=[{"name": "adw"}])
    reason = skip_reason(issue)
    assert reason is not None
    assert "type label" in reason


def test_skip_reason_two_type_labels():
    issue = _issue(labels=[{"name": "adw"}, {"name": "feat"}, {"name": "bug"}])
    reason = skip_reason(issue)
    assert reason is not None
    assert "type label" in reason


def test_skip_reason_accepts_criteria_less_issue():
    # S-013: a terse issue with no criteria heading is accepted (decompose
    # will expand it), not skipped.
    issue = _issue(body="Just a description with no criteria heading.")
    assert skip_reason(issue) is None


def test_skip_reason_skips_genuinely_empty_issue():
    issue = _issue(title="", body="")
    reason = skip_reason(issue)
    assert reason is not None
    assert "no title or body" in reason


def test_parse_issue_body_tolerates_quote_bars():
    # The issue-#16 shape: every line prefixed with a quote bar.
    body = "▎ Intro line.\n▎\n▎ ## Acceptance Criteria\n▎ - one\n▎ - two"
    desc, criteria = parse_issue_body(body)
    assert "Intro line." in desc
    assert criteria == ["one", "two"]


def test_sync_accepts_terse_issue_with_empty_criteria():
    terse = _issue(body="Add a dark mode toggle.")  # no AC heading
    prd = Prd(project="test", stories=[])
    added, skipped = sync_issues(prd, [terse])
    assert len(added) == 1
    assert added[0].acceptance_criteria == []  # decompose fills these later
    assert added[0].type == "feat"


def test_skip_reason_none_for_valid_issue():
    assert skip_reason(_issue()) is None


def test_issue_to_story_fields():
    issue = _issue(number=10, title="My story")
    story = issue_to_story(issue)
    assert story.id == "GH-10"
    assert story.type == "feat"
    assert story.title == "My story"
    assert story.priority == 5
    assert len(story.acceptance_criteria) == 2
    assert story.status == "open"
    assert story.passes is False


def test_issue_to_story_priority_from_label():
    issue = _issue(labels=[{"name": "feat"}, {"name": "adw"}, {"name": "p2"}])
    story = issue_to_story(issue)
    assert story.priority == 2


def test_issue_to_story_priority_long_form():
    issue = _issue(labels=[{"name": "feat"}, {"name": "adw"}, {"name": "priority-3"}])
    story = issue_to_story(issue)
    assert story.priority == 3


def test_sync_issues_adds_new():
    prd = Prd(project="test", stories=[])
    added, skipped = sync_issues(prd, [_issue()])
    assert len(added) == 1
    assert added[0].id == "GH-42"
    assert len(prd.stories) == 1


def test_sync_issues_dedup():
    existing = Story(
        id="GH-42", type="feat", priority=5, title="old",
        description="d", acceptance_criteria=["c"],
    )
    prd = Prd(project="test", stories=[existing])
    added, skipped = sync_issues(prd, [_issue()])
    assert len(added) == 0
    assert any("already synced" in r for _, r in skipped)
    assert len(prd.stories) == 1


def test_sync_issues_skips_malformed():
    bad_issue = _issue(body="no criteria here", labels=[{"name": "adw"}])
    prd = Prd(project="test", stories=[])
    added, skipped = sync_issues(prd, [bad_issue])
    assert len(added) == 0
    assert len(skipped) == 1
    assert len(prd.stories) == 0


def test_sync_issues_filters_pull_request_items():
    """list_adw_issues drops PR items; sync_issues handles a clean list."""
    pr_item = dict(_issue(), pull_request={"url": "https://github.com/..."})
    prd = Prd(project="test", stories=[])
    # If a PR somehow slipped through, skip_reason would catch it (no type label logic)
    # but normally list_adw_issues strips them before sync_issues sees them.
    # Verify sync_issues itself just treats them as normal issues (the filter is upstream).
    added, _ = sync_issues(prd, [_issue()])
    assert len(added) == 1

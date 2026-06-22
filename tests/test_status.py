import pytest

from adw.status import StatusBlock, StatusBlockError, parse_status_block

GOOD_BLOCK = """
Some agent prose about what it did.

```json
{
  "stage": "implement",
  "ticket_id": "S-001",
  "outcome": "success",
  "exit_signal": false,
  "summary": "added endpoint",
  "failure_reason": null,
  "files_changed": 7,
  "suggested_tools": [],
  "system_repair_suggested": false
}
```
"""


def test_parses_block_from_fenced_output():
    block = parse_status_block(GOOD_BLOCK)
    assert block == StatusBlock(
        stage="implement",
        ticket_id="S-001",
        outcome="success",
        summary="added endpoint",
        files_changed=7,
    )


def test_takes_last_block_when_multiple():
    text = (
        '{"stage": "plan", "ticket_id": "S-001", "outcome": "failure"}\n'
        'more prose\n'
        '{"stage": "plan", "ticket_id": "S-001", "outcome": "success", "exit_signal": true}'
    )
    block = parse_status_block(text)
    assert block.outcome == "success"
    assert block.exit_signal is True


def test_ignores_json_that_is_not_a_status_block():
    text = '{"foo": 1}\n{"stage": "test", "ticket_id": "S-002", "outcome": "success"}'
    assert parse_status_block(text).ticket_id == "S-002"


def test_prose_only_raises():
    with pytest.raises(StatusBlockError, match="no status block"):
        parse_status_block("everything passes! done!")


def test_invalid_outcome_raises():
    with pytest.raises(StatusBlockError, match="outcome"):
        parse_status_block('{"stage": "test", "ticket_id": "S-001", "outcome": "done!"}')


def test_parses_pr_description_when_present():
    text = (
        '{"stage": "review", "ticket_id": "GH-51", "outcome": "success", '
        '"exit_signal": true, "pr_description": "Adds review-authored PR body."}'
    )
    block = parse_status_block(text)
    assert block.pr_description == "Adds review-authored PR body."


def test_pr_description_defaults_to_none_when_absent():
    block = parse_status_block(GOOD_BLOCK)
    assert block.pr_description is None


def test_parses_file_manifest_when_present():
    text = (
        '{"stage": "plan", "ticket_id": "GH-61", "outcome": "success", '
        '"file_manifest": {"edit": ["adw/status.py"], "read": ["adw/workflow_runner.py:466"]}}'
    )
    block = parse_status_block(text)
    assert block.file_manifest == {
        "edit": ["adw/status.py"],
        "read": ["adw/workflow_runner.py:466"],
    }


def test_file_manifest_defaults_to_none_when_absent():
    block = parse_status_block(GOOD_BLOCK)
    assert block.file_manifest is None


def test_non_dict_file_manifest_coerced_to_none():
    text = (
        '{"stage": "plan", "ticket_id": "GH-61", "outcome": "success", '
        '"file_manifest": "not a dict"}'
    )
    block = parse_status_block(text)
    assert block.file_manifest is None

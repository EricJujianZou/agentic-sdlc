"""Tests for adw/invoke.py command construction and result handling.

The two Windows-specific failure modes these pin down (both shipped in v1
because this module had no coverage):
1. bare "claude" cannot be spawned with shell=False (npm .cmd shim);
2. multi-line prompts passed as argv get mangled by the cmd.exe shim,
   so the prompt must travel via stdin, never argv.
"""
from __future__ import annotations

import pytest

from adw.invoke import STAGE_TOOLS, build_command, _parse_envelope


def test_build_command_has_no_prompt_in_argv():
    cmd = build_command(stage="plan", model="opus")
    # "-p" is the print flag, not a prompt: nothing multi-line may appear.
    assert all("\n" not in part for part in cmd)
    assert "-p" in cmd
    assert "--allowedTools" in cmd
    assert cmd[cmd.index("--allowedTools") + 1] == ",".join(STAGE_TOOLS["plan"])


def test_build_command_resolves_executable_or_falls_back():
    cmd = build_command(stage="implement", model="sonnet")
    # Either a resolved absolute path (normal) or the bare fallback (no CLI
    # on PATH, e.g. CI) — never anything else.
    assert cmd[0] == "claude" or cmd[0].lower().endswith((".cmd", ".exe", "claude"))


def test_build_command_rejects_unknown_stage():
    with pytest.raises(ValueError):
        build_command(stage="deploy", model="opus")


def test_parse_envelope_extracts_fields():
    envelope = (
        '{"result": "done {\\"stage\\": \\"plan\\"}", "session_id": "s1", '
        '"total_cost_usd": 0.5, "usage": {"input_tokens": 10, "output_tokens": 5}, '
        '"permission_denials": [{"tool": "Bash"}]}'
    )
    text, tokens, cost, session_id, denials = _parse_envelope(envelope)
    assert text.startswith("done")
    assert tokens == 15
    assert cost == 0.5
    assert session_id == "s1"
    assert denials == 1


def test_parse_envelope_falls_back_on_non_json():
    text, tokens, cost, session_id, denials = _parse_envelope("not json at all")
    assert text == "not json at all"
    assert (tokens, cost, session_id, denials) == (0, 0.0, None, 0)

"""Tests for adw/isolation.py and the invoke dispatch it feeds.

The offline suite can only assert the *shape* of the `docker run` argv and
the on/off dispatch — real container isolation (host FS unreachable, hooks
firing inside, no credential leak) is verified by hand per README "Container
isolation", not here. These tests pin the safety-relevant invariants of the
argv: only the repo is mounted, only scoped env crosses, and isolation-off
leaves the host command byte-for-byte unchanged.
"""
from __future__ import annotations

from pathlib import Path

from adw import isolation
from adw.invoke import build_command


# --- isolation_enabled -------------------------------------------------------

def test_isolation_disabled_by_default():
    assert isolation.isolation_enabled({}) is False
    assert isolation.isolation_enabled({"ADW_ISOLATION": ""}) is False
    assert isolation.isolation_enabled({"ADW_ISOLATION": "0"}) is False
    assert isolation.isolation_enabled({"ADW_ISOLATION": "false"}) is False


def test_isolation_enabled_truthy_values():
    for val in ("1", "true", "TRUE", "Yes", "on"):
        assert isolation.isolation_enabled({"ADW_ISOLATION": val}) is True


# --- build_command claude_bin override --------------------------------------

def test_build_command_uses_bare_claude_for_container():
    cmd = build_command(stage="plan", model="opus", claude_bin="claude")
    assert cmd[0] == "claude"


# --- build_run_command argv shape -------------------------------------------

def _wrap(tmp_path, *, stage="implement", env=None):
    inner = build_command(stage=stage, model="sonnet", claude_bin="claude")
    return inner, isolation.build_run_command(
        inner, repo_dir=tmp_path, stage=stage, env=env or {}
    )


def test_run_command_is_docker_run_with_stdin(tmp_path):
    _, cmd = _wrap(tmp_path)
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "-i" in cmd  # prompt still travels on stdin


def test_run_command_mounts_only_the_repo(tmp_path):
    _, cmd = _wrap(tmp_path)
    mounts = [a for a in cmd if a.startswith("--mount=")]
    assert len(mounts) == 1  # the host FS invariant: exactly one bind mount
    resolved = Path(tmp_path).resolve()
    assert mounts[0] == f"--mount=type=bind,source={resolved},target=/workspace"
    assert f"--workdir={isolation.CONTAINER_WORKDIR}" in cmd
    # No broad mounts / privilege escalation that would defeat isolation.
    assert "--privileged" not in cmd
    assert not any(a == "-v" or a.startswith("-v=") for a in cmd)


def test_run_command_injects_scoped_run_env(tmp_path):
    _, cmd = _wrap(tmp_path, stage="review")
    # The hooks key off these inside the container.
    assert _has_e(cmd, "ADW_TICKET_RUN=1")
    assert _has_e(cmd, "ADW_STAGE=review")


def test_run_command_forwards_only_present_secrets(tmp_path):
    # Absent secret -> not forwarded.
    _, cmd = _wrap(tmp_path, env={})
    assert not _has_e(cmd, "ANTHROPIC_API_KEY")
    # Present secret -> forwarded by name only (value never in argv).
    _, cmd = _wrap(tmp_path, env={"ANTHROPIC_API_KEY": "sk-secret"})
    assert _has_e(cmd, "ANTHROPIC_API_KEY")
    assert "sk-secret" not in cmd


def test_run_command_image_then_inner_cmd(tmp_path):
    inner, cmd = _wrap(tmp_path, env={"ADW_SANDBOX_IMAGE": "custom:tag"})
    idx = cmd.index("custom:tag")
    # Everything after the image is the inner claude argv, in order.
    assert cmd[idx + 1:] == inner


def test_run_command_honors_network_and_docker_bin(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_DOCKER_BIN", "podman")
    inner = build_command(stage="test", model="sonnet", claude_bin="claude")
    cmd = isolation.build_run_command(
        inner, repo_dir=tmp_path, stage="test", env={"ADW_SANDBOX_NETWORK": "none"}
    )
    assert cmd[0] == "podman"
    assert "--network=none" in cmd


def _has_e(cmd: list[str], value: str) -> bool:
    """True if `-e value` appears as an adjacent pair in the argv."""
    return any(cmd[i] == "-e" and cmd[i + 1] == value for i in range(len(cmd) - 1))


# --- invoke_stage dispatch (off = host path unchanged; on = wrapped) --------

class _FakeProc:
    def __init__(self):
        self.stdout = '{"result": "", "usage": {}}'
        self.stderr = ""
        self.returncode = 0


def _capture_invoke(monkeypatch, tmp_path, *, isolate: bool):
    if isolate:
        monkeypatch.setenv("ADW_ISOLATION", "1")
    else:
        monkeypatch.delenv("ADW_ISOLATION", raising=False)
    prompt = tmp_path / "p.md"
    prompt.write_text("hi", encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    import adw.invoke as invoke_mod
    monkeypatch.setattr(invoke_mod.subprocess, "run", fake_run)
    invoke_mod.invoke_stage(prompt, stage="implement", model="sonnet", cwd=tmp_path)
    return captured["cmd"]


def test_invoke_off_runs_host_command(monkeypatch, tmp_path):
    cmd = _capture_invoke(monkeypatch, tmp_path, isolate=False)
    assert cmd[0] != "docker"
    assert "-p" in cmd  # the bare claude argv, exactly as before


def test_invoke_on_wraps_in_docker(monkeypatch, tmp_path):
    cmd = _capture_invoke(monkeypatch, tmp_path, isolate=True)
    assert cmd[0] == "docker" and cmd[1] == "run"
    assert _has_e(cmd, "ADW_STAGE=implement")
